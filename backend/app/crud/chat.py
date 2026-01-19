from typing import List, Optional, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, update
from sqlalchemy.orm import selectinload

from app.db.models import Conversation, Message, Document, MessageRole
from app.schemas import chat as schemas


class CRUDChat:
    async def create_conversation(
        self, db: AsyncSession, user_id: UUID, obj_in: schemas.ChatCreate
    ) -> schemas.ConversationDetail:
        """
        Creates a new conversation AND the first message.
        Returns the detailed schema view.
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

        await db.commit()
        await db.refresh(db_obj)

        # 3. Return the clean schema (reusing get_details logic)
        return await self.get_details(db, conversation_id=db_obj.id)

    async def get_details(
        self, db: AsyncSession, conversation_id: UUID, limit: int = 50, offset: int = 0
    ) -> Optional[schemas.ConversationDetail]:
        """
        Optimized fetch:
        1. Conversation Metadata
        2. Paginated Messages
        3. Unique Document Files (Grouped by Hash) - No chunks!
        """
        # 1. Fetch Conversation (Metadata only)
        stmt = select(Conversation).where(Conversation.id == conversation_id)
        result = await db.execute(stmt)
        conversation = result.scalars().first()

        if not conversation:
            return None

        # 2. Fetch Messages (With Pagination)
        msg_stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        msg_result = await db.execute(msg_stmt)
        messages = msg_result.scalars().all()

        # 3. Fetch Unique Documents (Group by Hash/Filename)
        # This prevents returning 100s of chunks for a single file.
        doc_stmt = (
            select(
                Document.filename,
                Document.file_path,
                Document.file_hash,
                func.min(Document.created_at).label("created_at"),
            )
            .where(Document.conversation_id == conversation_id)
            .where(Document.file_hash.isnot(None)) # Only files with hashes
            .group_by(Document.filename, Document.file_path, Document.file_hash)
        )
        doc_result = await db.execute(doc_stmt)

        # Map SQL rows to Pydantic Schema
        unique_docs = [
            schemas.DocumentFile(
                filename=row.filename,
                file_path=row.file_path,
                created_at=row.created_at,
                file_hash=row.file_hash,
            )
            for row in doc_result.all()
        ]

        # 4. Construct & Return Response
        return schemas.ConversationDetail(
            id=conversation.id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            messages=messages,
            documents=unique_docs,
        )

    async def get_multi_by_user(
        self, db: AsyncSession, user_id: UUID, skip: int = 0, limit: int = 20
    ) -> List[Conversation]:
        """
        Get list of conversations for dashboard (Metadata only).
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
        Add a message and update conversation timestamp.
        """
        # 1. Add Message
        db_msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=obj_in.content,
            metadata_=None,
        )
        db.add(db_msg)

        # 2. Touch the Conversation 'updated_at' field
        # This ensures the chat moves to the top of the list in the UI
        stmt_update = (
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=func.now())
        )
        await db.execute(stmt_update)

        await db.commit()
        await db.refresh(db_msg)
        return db_msg

    async def delete_conversation(
        self, db: AsyncSession, conversation_id: UUID, user_id: UUID
    ) -> bool:
        """
        Deletes a conversation only if it belongs to the specific user.
        Cascade rules in DB models should handle message/document deletion.
        """
        stmt = select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user_id
        )
        result = await db.execute(stmt)
        chat = result.scalars().first()

        if not chat:
            return False

        await db.delete(chat)
        await db.commit()
        return True


chat = CRUDChat()
