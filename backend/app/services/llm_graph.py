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
    doc_ids: Optional[List[UUID]]


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
    Node 2: Retrieve relevant chunks from Postgres (HNSW).
    """
    print("🤖 Graph Node: Retrieving Context...")
    query = state["user_query"]
    db = state["db_session"]
    chat_id = state["chat_id"]

    # [NEW] Check for filter in the last message metadata or passed state
    filter_ids = state.get("doc_ids", None)

    # 1. Embed
    query_vector = rag_service.embeddings.embed_query(query)

    # 2. Search - Only search in chunks (documents with embeddings)
    # Original documents have content_snippet like "Processing..." or "Processed (X chunks)"
    # Chunks have actual text content and embeddings
    # Note: Chunks should be in the same conversation, but we'll verify with debugging
    stmt = select(Document).where(
        Document.conversation_id == chat_id,
        Document.embedding.isnot(None)  # Only chunks have embeddings
    )
    
    # Debug: Count total chunks in conversation before filtering
    count_stmt = select(Document).where(
        Document.conversation_id == chat_id,
        Document.embedding.isnot(None)
    )
    count_result = await db.execute(count_stmt)
    total_chunks = len(count_result.scalars().all())
    print(f"🔍 Total chunks in conversation: {total_chunks}")

    # Apply Filter by file_hash if document IDs are provided
    if filter_ids:
        print(f"🎯 Filtering search to {len(filter_ids)} documents.")
        # Get file_hash values for the selected document IDs
        # Original documents have the file_hash, chunks share the same file_hash
        hash_stmt = select(Document.file_hash).where(
            Document.id.in_(filter_ids),
            Document.file_hash.isnot(None)
        ).distinct()
        hash_result = await db.execute(hash_stmt)
        file_hashes = [h for h in hash_result.scalars().all() if h]

        if file_hashes:
            print(f"📄 Found {len(file_hashes)} unique file(s) to search in. File hash(es): {file_hashes}")

            # Debug: Check how many chunks exist with this file_hash in THIS conversation
            debug_stmt = select(Document).where(
                Document.conversation_id == chat_id,
                Document.embedding.isnot(None),
                Document.file_hash.in_(file_hashes)
            )
            debug_result = await db.execute(debug_stmt)
            debug_chunks = debug_result.scalars().all()
            print(f"🔍 Debug: Found {len(debug_chunks)} chunks with matching file_hash in this conversation")

            # Debug: Check how many chunks exist with this file_hash in ANY conversation
            any_stmt = select(Document).where(
                Document.embedding.isnot(None),
                Document.file_hash.in_(file_hashes)
            ).limit(5)
            any_result = await db.execute(any_stmt)
            any_chunks = any_result.scalars().all()
            print(f"🔍 Debug: Found {len(any_chunks)} chunks with matching file_hash in ANY conversation")

            if debug_chunks or any_chunks:
                # Only apply the filter if we actually found matching chunks
                stmt = stmt.where(Document.file_hash.in_(file_hashes))
                print("✅ Applying file_hash filter to retrieval query.")
            else:
                # Fallback: do NOT filter by file_hash; use all chunks in conversation
                print("⚠️ No chunks have matching file_hash; falling back to all chunks in conversation.")
        else:
            # If no file_hash found, the documents might not be processed yet
            print("⚠️ Selected documents don't have file_hash yet (not processed). Falling back to all chunks.")

    # 3. Order by similarity and limit results
    stmt = stmt.order_by(Document.embedding.cosine_distance(query_vector)).limit(4)

    result = await db.execute(stmt)
    docs = result.scalars().all()

    context_text = "\n\n".join([d.content_snippet for d in docs if d.content_snippet]) if docs else ""
    print(f"📚 Retrieved {len(docs)} chunks with {len(context_text)} characters of context.")
    if context_text:
        print(f"📄 Context preview (first 200 chars): {context_text[:200]}...")
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
        return {"messages": [AIMessage(content="I cannot find that information in the documents.")]}

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
