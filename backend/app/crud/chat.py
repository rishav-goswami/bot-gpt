from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.db.models import Conversation, Message, User, MessageRole
from app.schemas import chat as schemas


class CRUDChat:
    async def create_conversation(
        self, db: AsyncSession, user_id: UUID, obj_in: schemas.ChatCreate
    ) -> Conversation:
        """
        Creates a new conversation AND the first message in one transaction.
        """
        # 1. Create Conversation Entry
        db_obj = Conversation(
            user_id=user_id,
            title=obj_in.first_message[:40] + "...",  # Simple title generation
        )
        db.add(db_obj)
        await db.flush()  # Generate ID without committing

        # 2. Add First Message
        first_msg = Message(
            conversation_id=db_obj.id,
            role=MessageRole.USER,
            content=obj_in.first_message,
        )
        db.add(first_msg)

        # 3. If a document was attached, link it (Logic to be expanded if needed)
        # if obj_in.document_id: ...

        await db.commit()
        await db.refresh(db_obj)

        # Reload to get the relationship populated
        return await self.get(db, conversation_id=db_obj.id)

    async def get(
        self, db: AsyncSession, conversation_id: UUID
    ) -> Optional[Conversation]:
        """
        Get a single conversation with all its messages.
        Note: Documents are loaded separately via get_by_conversation to filter chunks.
        """
        query = (
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(
                selectinload(Conversation.messages),
            )
        )
        result = await db.execute(query)
        return result.scalars().first()

    async def get_multi_by_user(
        self, db: AsyncSession, user_id: UUID, skip: int = 0, limit: int = 20
    ) -> List[Conversation]:
        """
        Get all conversations for a specific user (Pagination included).
        """
        query = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(desc(Conversation.updated_at))
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        return result.scalars().all()

    async def create_message(
        self,
        db: AsyncSession,
        conversation_id: UUID,
        obj_in: schemas.MessageCreate,
        role: MessageRole,
    ) -> Message:
        """
        Add a message to an existing conversation.
        """
        db_msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=obj_in.content,
            metadata_=None,  # Can pass metadata if needed
        )
        db.add(db_msg)

        # Update conversation timestamp
        # We assume the caller will commit, or we can commit here
        await db.commit()
        await db.refresh(db_msg)
        return db_msg

    async def delete_conversation(self, db: AsyncSession, conversation_id: UUID, user_id: UUID) -> bool:
        """
        Deletes a conversation only if it belongs to the specific user.
        Returns True if deleted, False if not found.
        """
        stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id
        )
        result = await db.execute(stmt)
        chat = result.scalars().first()

        if not chat:
            return False

        await db.delete(chat)
        await db.commit()
        return True


chat = CRUDChat()
