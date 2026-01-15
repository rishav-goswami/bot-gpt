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
        """
        Get only original documents (not chunks).
        Original documents are identified by:
        - content_snippet is "Processing..." or starts with "Processed"
        - OR they don't have embeddings (original uploads before processing)
        """
        from sqlalchemy import or_, func
        
        # Get all documents for this conversation
        all_docs_query = select(Document).where(
            Document.conversation_id == conversation_id
        )
        all_docs_result = await db.execute(all_docs_query)
        all_docs = all_docs_result.scalars().all()
        
        # Filter to get only original documents (one per file_hash)
        # Original documents have content_snippet that is "Processing..." or starts with "Processed"
        # OR they don't have embeddings
        original_docs_by_hash = {}
        original_docs_by_id = {}
        
        for doc in all_docs:
            # Check if this is an original document (not a chunk)
            # Original documents have:
            # - content_snippet == "Processing..." (just uploaded)
            # - content_snippet starts with "Processed" (processed)
            # - No embedding (original upload before processing)
            # Chunks have embeddings AND actual text content (not "Processing..." or "Processed...")
            # Original documents are identified by:
            # 1. content_snippet is "Processing..." (just uploaded)
            # 2. content_snippet starts with "Processed" (processed)
            # 3. No embedding AND content_snippet is not a long text (original upload before processing)
            # Chunks have embeddings AND long text content (not "Processing..." or "Processed...")
            is_original = (
                doc.content_snippet == "Processing..." or
                (doc.content_snippet and doc.content_snippet.startswith("Processed")) or
                (doc.embedding is None and doc.content_snippet and 
                 doc.content_snippet != "Processing..." and 
                 len(doc.content_snippet) < 200)  # Original docs have short snippets or status messages
            )
            
            if is_original:
                if doc.file_hash:
                    # Group by file_hash, keep the one with "Processed" status if available
                    if doc.file_hash not in original_docs_by_hash:
                        original_docs_by_hash[doc.file_hash] = doc
                    elif doc.content_snippet and doc.content_snippet.startswith("Processed"):
                        # Prefer processed status over processing
                        original_docs_by_hash[doc.file_hash] = doc
                else:
                    # Documents without file_hash (just uploaded, not processed yet)
                    # Use id as key to keep unique
                    if doc.id not in original_docs_by_id:
                        original_docs_by_id[doc.id] = doc
        
        # Combine results
        result = list(original_docs_by_hash.values()) + list(original_docs_by_id.values())
        return result


document = CRUDDocument()
