from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import Document
from app.schemas import document as schemas


class CRUDDocument:
    async def create(
        self, db: AsyncSession, obj_in: schemas.DocumentCreate
    ) -> Document:
        db_obj = Document(
            filename=obj_in.filename,
            file_path=obj_in.file_path,
            conversation_id=obj_in.conversation_id,
            content_snippet=obj_in.content_snippet,
            # embedding is handled separately by the worker
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def get_by_conversation(
        self, db: AsyncSession, conversation_id: UUID
    ) -> List[Document]:
        query = select(Document).where(Document.conversation_id == conversation_id)
        result = await db.execute(query)
        return result.scalars().all()


document = CRUDDocument()
