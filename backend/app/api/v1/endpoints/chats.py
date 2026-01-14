from typing import List, Any, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api import deps
from app.db.models import User, MessageRole, Document, Conversation, Message
from app.schemas import chat as schemas
from app.crud import chat as crud
from app.llm_client import llm_client
from app.services.socketio_manager import sio
from app.services.rag_service import rag_service
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.services.llm_graph import app_graph 

router = APIRouter()


async def run_chat_graph(
    db: AsyncSession, 
    chat: Conversation, 
    user_content: str
) -> Message:
    """
    Executes the LangGraph workflow.
    """
    # 1. Prepare LangChain formatted messages (History)
    # Sliding window: last 10
    recent_msgs = chat.messages[-10:] if chat.messages else []
    lc_messages = []
    for m in recent_msgs:
        if m.role == MessageRole.USER:
            lc_messages.append(HumanMessage(content=m.content))
        elif m.role == MessageRole.ASSISTANT:
            lc_messages.append(AIMessage(content=m.content))
    
    # Add current user message if not already there
    if not lc_messages or lc_messages[-1].content != user_content:
        lc_messages.append(HumanMessage(content=user_content))

    # 2. Invoke Graph
    print(f"🚀 Invoking LangGraph for Chat {chat.id}")
    inputs = {
        "messages": lc_messages,
        "user_query": user_content,
        "chat_id": chat.id,
        "db_session": db, # Passing DB session into graph state
        "context": "",
        "has_documents": False
    }
    
    result = await app_graph.ainvoke(inputs)
    
    # 3. Extract AI Response
    # The graph returns the updated state. The last message is the AI's response.
    ai_response_content = result["messages"][-1].content

    # 4. Save to DB
    ai_msg_in = schemas.MessageCreate(content=ai_response_content, role=MessageRole.ASSISTANT)
    ai_msg = await crud.chat.create_message(
        db, conversation_id=chat.id, obj_in=ai_msg_in, role=MessageRole.ASSISTANT
    )

    # 5. Emit to Socket
    await sio.emit_to_room(
        room=str(chat.id),
        event="new_message",
        data=schemas.MessageResponse.model_validate(ai_msg).model_dump(mode="json"),
    )
    
    return ai_msg

# --- ENDPOINTS ---


@router.post("/", response_model=schemas.ConversationDetail, status_code=201)
async def create_conversation(
    chat_in: schemas.ChatCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    # 1. Create Conversation & Save First User Message
    new_chat = await crud.chat.create_conversation(
        db=db, user_id=current_user.id, obj_in=chat_in
    )

    # 2. [NEW] Trigger LLM immediately for the first message
    # We emit the user message first so the UI updates nicely
    if new_chat.messages:
        first_msg = new_chat.messages[0]
        await sio.emit_to_room(
            room=str(new_chat.id),
            event="new_message",
            data=schemas.MessageResponse.model_validate(first_msg).model_dump(
                mode="json"
            ),
        )

    # 3. Generate AI Reply
    await run_chat_graph(db, new_chat, chat_in.first_message)

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
    # 1. Validate Chat
    chat = await crud.chat.get(db, conversation_id=chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # 2. Save & Emit User Message
    user_msg = await crud.chat.create_message(
        db, conversation_id=chat_id, obj_in=msg_in, role=MessageRole.USER
    )

    await sio.emit_to_room(
        room=str(chat_id),
        event="new_message",
        data=schemas.MessageResponse.model_validate(user_msg).model_dump(mode="json"),
    )

    # 3. Refresh chat context in memory
    # We append the new message to the loaded object so the LLM sees it in history
    chat.messages.append(user_msg)

    # 4. Generate AI Reply using the helper
    ai_msg = await run_chat_graph(db, chat, msg_in.content)

    return ai_msg


@router.delete("/{chat_id}", status_code=204)
async def delete_conversation(
    chat_id: UUID, db: AsyncSession = Depends(deps.get_db)
) -> None:
    chat = await crud.chat.get(db, conversation_id=chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await crud.chat.delete(db, conversation_id=chat_id)
