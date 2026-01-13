from typing import List, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api import deps
from app.db.models import User, MessageRole
from app import schemas
from app import crud
from app.llm_client import llm_client
from app.services.socketio_manager import sio
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

router = APIRouter()


# --- 1. Start a New Conversation ---
@router.post("/", response_model=schemas.ConversationDetail, status_code=201)
async def create_conversation(
    chat_in: schemas.ChatCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Create a new conversation session and save the first message.
    """
    new_chat = await crud.chat.create_conversation(
        db=db, user_id=current_user.id, obj_in=chat_in
    )
    return new_chat


# --- 2. List Conversations ---
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


# --- 3. Get Conversation Detail ---
@router.get("/{chat_id}", response_model=schemas.ConversationDetail)
async def get_conversation(
    chat_id: UUID, db: AsyncSession = Depends(deps.get_db)
) -> Any:
    chat = await crud.chat.get(db, conversation_id=chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return chat


# --- 4. Send Message (REST + Realtime Emit) ---
@router.post("/{chat_id}/messages", response_model=schemas.MessageResponse)
async def send_message(
    chat_id: UUID,
    msg_in: schemas.MessageCreate,
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    1. User sends message -> Saved to DB -> Emitted to Socket Room.
    2. Backend fetches history -> Calls LLM.
    3. LLM responds -> Saved to DB -> Emitted to Socket Room -> Returned.
    """
    # A. Validate Chat Exists
    chat = await crud.chat.get(db, conversation_id=chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # B. Save & Emit User Message
    user_msg = await crud.chat.create_message(
        db, conversation_id=chat_id, obj_in=msg_in, role=MessageRole.USER
    )

    # [Socket.IO] Notify clients (Real-time update)
    # We serialize the Pydantic model to dict/json for the socket event
    await sio.emit_to_room(
        room=str(chat_id),
        event="new_message",
        data=schemas.MessageResponse.model_validate(user_msg).model_dump(mode="json"),
    )

    # C. Build Context for LLM (History)
    # Sliding window: last 10 messages
    history_messages = [
        SystemMessage(content="You are a helpful AI assistant for Bot Consulting.")
    ]
    recent_msgs = chat.messages[-10:]

    for m in recent_msgs:
        if m.role == MessageRole.USER:
            history_messages.append(HumanMessage(content=m.content))
        elif m.role == MessageRole.ASSISTANT:
            history_messages.append(AIMessage(content=m.content))

    # Ensure current message is in history
    if not history_messages or history_messages[-1].content != msg_in.content:
        history_messages.append(HumanMessage(content=msg_in.content))

    # D. Call LLM
    try:
        llm = llm_client.get_llm()
        ai_response = llm.invoke(history_messages)
        ai_text = ai_response.content
    except Exception as e:
        print(f"LLM Error: {e}")
        ai_text = "I'm sorry, I'm having trouble connecting to my brain right now."

    # E. Save & Emit Assistant Response
    ai_msg_in = schemas.MessageCreate(content=ai_text, role=MessageRole.ASSISTANT)
    ai_msg = await crud.chat.create_message(
        db, conversation_id=chat_id, obj_in=ai_msg_in, role=MessageRole.ASSISTANT
    )

    # [Socket.IO] Notify clients
    await sio.emit_to_room(
        room=str(chat_id),
        event="new_message",
        data=schemas.MessageResponse.model_validate(ai_msg).model_dump(mode="json"),
    )

    return ai_msg


# --- 5. Delete Conversation ---
@router.delete("/{chat_id}", status_code=204)
async def delete_conversation(
    chat_id: UUID, db: AsyncSession = Depends(deps.get_db)
) -> None:
    chat = await crud.chat.get(db, conversation_id=chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await crud.chat.delete(db, conversation_id=chat_id)
