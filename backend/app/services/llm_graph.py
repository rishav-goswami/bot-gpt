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
    # For simplicity, let's assume we extract it from the last message payload
    # (In a real app, you'd pass this via state explicitly)
    filter_ids = state.get(
        "doc_ids", None
    )  # You need to add doc_ids to GraphState TypedDict

    # 1. Embed
    query_vector = rag_service.embeddings.embed_query(query)

    # 2. Search
    stmt = select(Document).where(Document.conversation_id == chat_id)

    # Apply Filter
    if filter_ids:
        print(f"🎯 Filtering search to {len(filter_ids)} documents.")
        stmt = stmt.where(Document.id.in_(filter_ids))

    stmt = stmt.order_by(Document.embedding.cosine_distance(query_vector)).limit(4)

    result = await db.execute(stmt)
    docs = result.scalars().all()

    context_text = "\n\n".join([d.content_snippet for d in docs]) if docs else ""
    return {"context": context_text}


async def generate_rag(state: GraphState):
    """
    Node 3a: Generate Answer using RAG Context.
    """
    print("🤖 Graph Node: Generating RAG Response...")

    # Load Prompt from YAML
    system_template = prompt_manager.load_prompt("chat.yaml", "rag_system")
    system_msg = system_template.format(
        context=state.get("context", "No context found.")
    )

    messages = [SystemMessage(content=system_msg)] + state["messages"]

    llm = llm_client.get_llm()
    response = llm.invoke(messages)

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
