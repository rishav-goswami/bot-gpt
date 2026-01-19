import json
from typing import TypedDict, List, Annotated, Optional
from uuid import UUID

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.prompts import prompt_manager
from app.llm_client import llm_client
from app.services.rag_service import rag_service
from app.db.models import Document, Conversation


# --- 1. Define the State ---
class GraphState(TypedDict):
    """The state of our execution graph."""

    messages: List[BaseMessage]
    user_query: str
    chat_id: UUID
    db_session: AsyncSession  # We pass the DB session through the graph
    context: str
    has_documents: bool
    doc_ids: Optional[List[str]]  # this is file_hash list to filter retrieval


# --- 2. Define Nodes ---


async def check_documents(state: GraphState):
    """
    Node 1: Check if this chat even has documents attached.
    """
    print("🤖 Graph Node: Checking Documents...")
    db = state["db_session"]
    chat_id = state["chat_id"]

    # Check DB for any docs linked to this chat
    stmt = select(Document.id).where(Document.conversation_id == chat_id).limit(1)
    result = await db.execute(stmt)
    has_docs = result.scalars().first() is not None

    return {"has_documents": has_docs}


async def retrieve(state: GraphState):
    """
    Node 2: Retrieve relevant chunks from Postgres (HNSW) and format with Metadata.
    """
    print("🤖 Graph Node: Retrieving Context...")

    query = state["user_query"]
    db = state["db_session"]
    chat_id = state["chat_id"]
    filter_hashes = state.get("doc_ids", None)

    # --- [DEBUG START] for Demo Purposes ---
    # This block proves your filtering logic works during the presentation
    count_stmt = select(Document).where(
        Document.conversation_id == chat_id, Document.embedding.isnot(None)
    )
    count_result = await db.execute(count_stmt)
    total_chunks = len(count_result.scalars().all())
    print(f"🔍 [DEBUG] Total chunks available in this chat: {total_chunks}")
    # --- [DEBUG END] ---

    # 1. Embed the User Query
    query_vector = rag_service.embeddings.embed_query(query)

    # 2. Build the Base Query
    stmt = select(Document).where(
        Document.conversation_id == chat_id,
        Document.embedding.isnot(None),
    )

    # 3. Apply Filters (Select-to-Talk)
    if filter_hashes:
        print(f"🎯 [FILTER] Restricting search to file hashes: {filter_hashes}")

        # [DEBUG] Verify if these hashes actually exist in the DB
        check_stmt = (
            select(Document.id)
            .where(
                Document.conversation_id == chat_id,
                Document.file_hash.in_(filter_hashes),
            )
            .limit(1)
        )
        check_res = await db.execute(check_stmt)
        if not check_res.scalars().first():
            print(
                f"⚠️ [WARNING] The requested file hashes {filter_hashes} were NOT found in this chat's context!"
            )

        stmt = stmt.where(Document.file_hash.in_(filter_hashes))

    # 4. Vector Search
    stmt = stmt.order_by(Document.embedding.cosine_distance(query_vector)).limit(4)

    # 5. Execute
    result = await db.execute(stmt)
    docs = result.scalars().all()

    # 6. Format Context with Metadata for Citations
    formatted_chunks = []

    if not docs:
        print("⚠️ No relevant documents found.")
        return {"context": ""}

    for doc in docs:
        # Handle Legacy Data
        meta = doc.doc_metadata if doc.doc_metadata else {}

        source_file = meta.get("source", doc.filename)
        page_num = meta.get("page_number", "N/A")

        # XML-style block for high precision
        chunk_block = (
            f"<document source='{source_file}' page='{page_num}'>\n"
            f"{doc.content_snippet}\n"
            f"</document>"
        )
        formatted_chunks.append(chunk_block)

    context_text = "\n\n".join(formatted_chunks)

    print(f"📚 Retrieved {len(docs)} chunks.")
    print(f"📄 Context preview: {context_text[:200]}...")

    return {"context": context_text}


async def generate_rag(state: GraphState):
    """
    Node 3a: Generate Answer using RAG Context.
    """
    print("🤖 Graph Node: Generating RAG Response...")

    context = state.get("context", "")
    print(f"📋 Context length: {len(context)} characters")
    if not context or len(context.strip()) == 0:
        print("⚠️ WARNING: Empty context! LLM will not have document information.")
        return {
            "messages": [
                AIMessage(content="I cannot find that information in the documents.")
            ]
        }

    # Load Prompt from YAML
    system_template = prompt_manager.load_prompt("chat.yaml", "rag_system")
    system_msg = system_template.format(context=context)

    print(f"📝 System prompt length: {len(system_msg)} characters")
    print(f"💬 User query: {state.get('user_query', 'N/A')}")

    messages = [SystemMessage(content=system_msg)] + state["messages"]

    llm = llm_client.get_llm()
    response = llm.invoke(messages)

    print(f"✅ LLM Response: {response.content[:100]}...")

    return {"messages": [response]}


async def generate_chat(state: GraphState):
    """
    Node 3b: General Conversation (No RAG).
    """
    print("🤖 Graph Node: Generating Casual Response...")

    system_template = prompt_manager.load_prompt("chat.yaml", "chat_system")
    # We could summarize history here, but for now we just pass it
    system_msg = system_template.format(history="See messages below.")

    messages = [SystemMessage(content=system_msg)] + state["messages"]

    llm = llm_client.get_llm()
    response = llm.invoke(messages)

    return {"messages": [response]}


# --- 3. Define Conditional Logic ---


def route_request(state: GraphState):
    """
    Edge: Decides where to go next.
    """
    if state["has_documents"]:
        return "retrieve"
    return "generate_chat"


# --- 4. Build the Graph ---

workflow = StateGraph(GraphState)

workflow.add_node("check_documents", check_documents)
workflow.add_node("retrieve", retrieve)
workflow.add_node("generate_rag", generate_rag)
workflow.add_node("generate_chat", generate_chat)

# Entry Point
workflow.set_entry_point("check_documents")

# Conditional Edge
workflow.add_conditional_edges(
    "check_documents",
    route_request,
    {"retrieve": "retrieve", "generate_chat": "generate_chat"},
)

# Normal Edges
workflow.add_edge("retrieve", "generate_rag")
workflow.add_edge("generate_rag", END)
workflow.add_edge("generate_chat", END)

# Compile
app_graph = workflow.compile()
