import os
import hashlib
from typing import List, Dict, Any
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# LangChain Imports
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings

# Models & Config
from app.db.models import Document
from app.core.config import settings

# NOTE: Removed 'sio' and 'AsyncSessionLocal' to prevent Event Loop crashes


class RAGService:
    def __init__(self):
        if settings.OPENAI_API_KEY:
            self.embeddings = OpenAIEmbeddings(
                model=settings.EMBEDDING_MODEL, openai_api_key=settings.OPENAI_API_KEY
            )
        else:
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )

    async def process_document(
        self,
        doc_id: UUID,
        file_path: str,
        conversation_id: UUID,
        db: AsyncSession,  # <--- CRITICAL FIX: Receive session from caller
    ) -> Dict[str, Any]:

        print(f"📄 Processing PDF: {file_path}")

        # 1. Calculate File Hash
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        file_hash = hash_md5.hexdigest()
        
        # 1.5 Check if file exists in THIS conversation
        stmt_check = select(Document).where(
            Document.conversation_id == conversation_id,
            Document.file_hash == file_hash
        ).limit(1)
        res_check = await db.execute(stmt_check)
        if res_check.scalars().first():
             print(f"⚠️ File {file_path} already exists in conversation {conversation_id}. Skipping.")
             return {"status": "exists", "chunks": 0, "cached": True}
        
        # 2. Check for Global Deduplication (using passed 'db')
        stmt = select(Document).where(Document.file_hash == file_hash).limit(1)
        result = await db.execute(stmt)
        existing_doc = result.scalars().first()

        if existing_doc:
            print(
                f"♻️ Cache Hit! File {file_path} (Hash: {file_hash}) processed previously."
            )

            # Fetch old chunks
            stmt_all = select(Document).where(Document.file_hash == file_hash)
            existing_chunks_result = await db.execute(stmt_all)
            existing_chunks = existing_chunks_result.scalars().all()

            # Copy vectors to new rows
            new_chunks = []
            for old_chunk in existing_chunks:
                new_chunk = Document(
                    conversation_id=conversation_id,
                    filename=os.path.basename(file_path),
                    file_path=file_path,
                    content_snippet=old_chunk.content_snippet,
                    embedding=old_chunk.embedding,  # Reuse vector
                    file_hash=file_hash,
                )
                db.add(new_chunk)
                new_chunks.append(new_chunk)

            # Update original document status
            original_doc = await db.get(Document, doc_id)
            if original_doc:
                original_doc.content_snippet = f"Processed ({len(new_chunks)} chunks)"
                original_doc.file_hash = file_hash  # Ensure file_hash is set
            
            await db.commit()
            print(f"✅ Copied {len(new_chunks)} chunks from cache.")

            # Return stats instead of emitting socket directly
            return {"status": "completed", "chunks": len(new_chunks), "cached": True}

        # 3. Cache Miss: Process normally
        print("🆕 New File. Generating Embeddings...")
        loader = PyMuPDFLoader(file_path)
        pages = loader.load()

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200
        )
        chunks = text_splitter.split_documents(pages)

        texts = [c.page_content for c in chunks]
        vectors = self.embeddings.embed_documents(texts)

        for text, vector in zip(texts, vectors):
            chunk_doc = Document(
                conversation_id=conversation_id,
                filename=os.path.basename(file_path),
                file_path=file_path,
                content_snippet=text,
                embedding=vector,
                file_hash=file_hash,
            )
            db.add(chunk_doc)

        # Update original document status
        original_doc = await db.get(Document, doc_id)
        if original_doc:
            original_doc.content_snippet = f"Processed ({len(chunks)} chunks)"
            original_doc.file_hash = file_hash  # Ensure file_hash is set
        
        await db.commit()
        print("✅ Embeddings saved to Postgres.")

        return {"status": "completed", "chunks": len(chunks), "cached": False}


rag_service = RAGService()
