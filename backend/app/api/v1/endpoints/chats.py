from typing import List, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api import deps
from app.db.models import User, MessageRole, Document
from app.schemas import chat as schemas
from app import crud
from app.llm_client import llm_client
from app.services.socketio_manager import sio
from app.services.rag_service import rag_service  # Needed for embedding the query
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

router = APIRouter()


def get_chat_history_window(messages: List[Any], window_size: int = 10) -> List[Any]:
    """
    Cost Optimization #1: Sliding Window.
    """
    system_prompt = SystemMessage(
        content="You are a helpful AI assistant for Bot Consulting. "
        "If context is provided, answer based ONLY on that context."
    )
    # Slice last N messages
    recent_msgs = messages[-window_size:]

    formatted_history = [system_prompt]
    for m in recent_msgs:
        if m.role == MessageRole.USER:
            formatted_history.append(HumanMessage(content=m.content))
        elif m.role == MessageRole.ASSISTANT:
            formatted_history.append(AIMessage(content=m.content))

    return formatted_history


async def retrieve_context(
    db: AsyncSession, conversation_id: UUID, query: str, k: int = 3
) -> str:
    """
    Performs HNSW Vector Search using pgvector.
    """
    # 1. Embed Query
    query_vector = rag_service.embeddings.embed_query(query)

    # 2. HNSW Search (Cosine Distance)
    stmt = (
        select(Document)
        .where(Document.conversation_id == conversation_id)
        .order_by(Document.embedding.cosine_distance(query_vector))
        .limit(k)
    )
    result = await db.execute(stmt)
    docs = result.scalars().all()

    if not docs:
        return ""

    context_text = "\n\n---\n".join([d.content_snippet for d in docs])
    return f"CONTEXT FROM UPLOADED DOCUMENTS:\n{context_text}\n---\n"


# --- Endpoints ---

@router.post("/", response_model=schemas.ConversationDetail, status_code=201)
async def create_conversation(
    chat_in: schemas.ChatCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    new_chat = await crud.chat.create_conversation(
        db=db, user_id=current_user.id, obj_in=chat_in
    )
    return new_chat


@router.get("/", response_model=List[schemas.ConversationSummary])
async def list_conversations(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    return await crud.chat.get_multi_by_user(
        db=db, user_id=current_user.id, skip=skip, limit=limit
    )


@router.get("/{chat_id}", response_model=schemas.ConversationDetail)
async def get_conversation(
    chat_id: UUID, db: AsyncSession = Depends(deps.get_db)
) -> Any:
    chat = await crud.chat.get(db, conversation_id=chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return chat


@router.post("/{chat_id}/messages", response_model=schemas.MessageResponse)
async def send_message(
    chat_id: UUID,
    msg_in: schemas.MessageCreate,
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    # A. Validate Chat
    chat = await crud.chat.get(db, conversation_id=chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # B. Save & Emit User Message
    user_msg = await crud.chat.create_message(
        db, conversation_id=chat_id, obj_in=msg_in, role=MessageRole.USER
    )

    await sio.emit_to_room(
        room=str(chat_id),
        event="new_message",
        data=schemas.MessageResponse.model_validate(user_msg).model_dump(mode="json"),
    )

    # C. RAG Retrieval (Vector Search)
    retrieved_context = ""
    # Only search if documents exist in this chat to save time
    if chat.documents:
        print(f"🔎 Performing HNSW Vector Search for: {msg_in.content}")
        retrieved_context = await retrieve_context(db, chat_id, msg_in.content)

    # D. Build LLM Context (Sliding Window + RAG)
    history_messages = get_chat_history_window(chat.messages, window_size=10)

    # Inject Context if found
    if retrieved_context:
        # Augment the last user message with context
        last_msg = history_messages[-1]
        augmented_content = f"{retrieved_context}\n\nUSER QUESTION: {msg_in.content}"

        if isinstance(last_msg, HumanMessage):
            last_msg.content = augmented_content
        else:
            history_messages.append(HumanMessage(content=augmented_content))
    else:
        # Ensure user message is appended if window slicing cut it off
        if not history_messages or history_messages[-1].content != msg_in.content:
            history_messages.append(HumanMessage(content=msg_in.content))

    # E. Call LLM
    try:
        llm = llm_client.get_llm()
        ai_response = llm.invoke(history_messages)
        ai_text = ai_response.content
    except Exception as e:
        print(f"❌ LLM Error: {e}")
        ai_text = "I'm sorry, I'm having trouble connecting to my brain right now."

    # F. Save & Emit Assistant Response
    ai_msg_in = schemas.MessageCreate(content=ai_text, role=MessageRole.ASSISTANT)
    ai_msg = await crud.chat.create_message(
        db, conversation_id=chat_id, obj_in=ai_msg_in, role=MessageRole.ASSISTANT
    )

    await sio.emit_to_room(
        room=str(chat_id),
        event="new_message",
        data=schemas.MessageResponse.model_validate(ai_msg).model_dump(mode="json"),
    )

    return ai_msg


@router.delete("/{chat_id}", status_code=204)
async def delete_conversation(
    chat_id: UUID, db: AsyncSession = Depends(deps.get_db)
) -> None:
    chat = await crud.chat.get(db, conversation_id=chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await crud.chat.delete(db, conversation_id=chat_id)
