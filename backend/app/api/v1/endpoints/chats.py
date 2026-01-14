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

router = APIRouter()


# --- HELPER: Reusable LLM Generation Logic ---
async def generate_and_save_ai_response(
    db: AsyncSession, chat: Conversation, user_content: str
) -> Message:
    """
    Core Logic: RAG Search -> Context Injection -> LLM Call -> Save -> Emit
    """
    chat_id = chat.id

    # 1. RAG Retrieval (Vector Search)
    retrieved_context = ""
    # We check if docs exist.
    if chat.documents:
        print(f"🔎 Performing HNSW Vector Search for: {user_content}")
        # Embed query
        query_vector = rag_service.embeddings.embed_query(user_content)
        # Search
        stmt = (
            select(Document)
            .where(Document.conversation_id == chat_id)
            .order_by(Document.embedding.cosine_distance(query_vector))
            .limit(3)
        )
        result = await db.execute(stmt)
        docs = result.scalars().all()

        if docs:
            context_text = "\n\n---\n".join([d.content_snippet for d in docs])
            retrieved_context = (
                f"CONTEXT FROM UPLOADED DOCUMENTS:\n{context_text}\n---\n"
            )
    system_instruction = (
        "You are a specialized RAG Assistant. "
        "Use the provided 'CONTEXT' to answer the user's question. "
        "If the answer is not in the context, say 'I cannot find that information in the documents.' "
        "Do not hallucinate or use outside knowledge. "
        "Keep answers concise and professional."
    )
    # 2. Build Context (Sliding Window)
    # We take the last 10 messages from the chat object
    system_prompt = SystemMessage(content=system_instruction)

    # Ensure we are working with a list
    recent_msgs = chat.messages[-10:] if chat.messages else []

    history_messages = [system_prompt]
    for m in recent_msgs:
        if m.role == MessageRole.USER:
            history_messages.append(HumanMessage(content=m.content))
        elif m.role == MessageRole.ASSISTANT:
            history_messages.append(AIMessage(content=m.content))

    # Inject Context into the specific user message in history
    # If the last message in history matches our current input, augment it.
    if (
        history_messages
        and isinstance(history_messages[-1], HumanMessage)
        and history_messages[-1].content == user_content
    ):
        if retrieved_context:
            history_messages[-1].content = (
                f"{retrieved_context}\n\nUSER QUESTION: {user_content}"
            )
    else:
        # Fallback: Append it if it wasn't found in the slice (e.g. very long history)
        full_content = (
            f"{retrieved_context}\n\nUSER QUESTION: {user_content}"
            if retrieved_context
            else user_content
        )
        history_messages.append(HumanMessage(content=full_content))

    # 3. Call LLM
    try:
        llm = llm_client.get_llm()
        ai_response = llm.invoke(history_messages)
        ai_text = ai_response.content
    except Exception as e:
        print(f"❌ LLM Error: {e}")
        ai_text = "I'm sorry, I'm having trouble connecting to my brain right now."

    # 4. Save Assistant Response
    ai_msg_in = schemas.MessageCreate(content=ai_text, role=MessageRole.ASSISTANT)
    ai_msg = await crud.chat.create_message(
        db, conversation_id=chat_id, obj_in=ai_msg_in, role=MessageRole.ASSISTANT
    )

    # 5. Emit to Socket
    await sio.emit_to_room(
        room=str(chat_id),
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
    await generate_and_save_ai_response(db, new_chat, chat_in.first_message)

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
    ai_msg = await generate_and_save_ai_response(db, chat, msg_in.content)

    return ai_msg


@router.delete("/{chat_id}", status_code=204)
async def delete_conversation(
    chat_id: UUID, db: AsyncSession = Depends(deps.get_db)
) -> None:
    chat = await crud.chat.get(db, conversation_id=chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await crud.chat.delete(db, conversation_id=chat_id)
