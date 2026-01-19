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
        db: AsyncSession,
    ) -> Dict[str, Any]:

        print(f"📄 Processing PDF: {file_path}")

        # 1. Calculate File Hash
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        file_hash = hash_md5.hexdigest()

        # 1.5 Check if file exists in THIS conversation (Idempotency)
        stmt_check = (
            select(Document)
            .where(
                Document.conversation_id == conversation_id,
                Document.file_hash == file_hash,
            )
            .limit(1)
        )
        res_check = await db.execute(stmt_check)
        if res_check.scalars().first():
            print(f"⚠️ File exists in conversation {conversation_id}. Skipping.")
            return {"status": "exists", "chunks": 0, "cached": True}

        # 2. Check for Global Deduplication (Reuse Embeddings)
        stmt = select(Document).where(Document.file_hash == file_hash).limit(1)
        result = await db.execute(stmt)
        existing_doc = result.scalars().first()

        if existing_doc:
            print(f"♻️ Cache Hit! File Hash {file_hash} found.")

            stmt_all = select(Document).where(Document.file_hash == file_hash)
            existing_chunks_result = await db.execute(stmt_all)
            existing_chunks = existing_chunks_result.scalars().all()

            new_chunks = []
            for old_chunk in existing_chunks:
                new_chunk = Document(
                    conversation_id=conversation_id,
                    filename=os.path.basename(file_path),
                    file_path=file_path,
                    content_snippet=old_chunk.content_snippet,
                    embedding=old_chunk.embedding,
                    file_hash=file_hash,
                    doc_metadata=old_chunk.doc_metadata,  # Reuse metadata
                )
                db.add(new_chunk)
                new_chunks.append(new_chunk)

            await db.commit()
            print(f"✅ Copied {len(new_chunks)} chunks from cache.")
            return {"status": "completed", "chunks": len(new_chunks), "cached": True}

        # 3. Cache Miss: Flatten & Chunk Strategy
        print("🆕 New File. Flattening & Generating Embeddings...")

        loader = PyMuPDFLoader(file_path)
        pages = loader.load()

        
        # Join all pages with double newlines. This treats the document as one
        # continuous stream, fixing issues where sentences span across pages.
        full_text = "\n\n".join([p.page_content for p in pages])

       
        # chunk_size=1000 (chars) ~= 250 tokens.
        # This is ideal for answering specific questions 
        # without losing the surrounding context.
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,  # 20% overlap ensures context isn't cut off
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )

        text_chunks = text_splitter.split_text(full_text)
        vectors = self.embeddings.embed_documents(text_chunks)

        # Batch Insert
        for i, (text, vector) in enumerate(zip(text_chunks, vectors)):

            # Simple metadata for standard bots
            # We lose "Exact Page Number" but gain "Contextual Accuracy"
            meta = {
                "source": os.path.basename(file_path),
                "chunk_index": i,
                "total_chunks": len(text_chunks),
            }

            chunk_doc = Document(
                conversation_id=conversation_id,
                filename=os.path.basename(file_path),
                file_path=file_path,
                content_snippet=text,
                embedding=vector,
                file_hash=file_hash,
                doc_metadata=meta,
            )
            db.add(chunk_doc)

        await db.commit()
        print(f"✅ Saved {len(text_chunks)} chunks to Postgres.")

        return {"status": "completed", "chunks": len(text_chunks), "cached": False}


rag_service = RAGService()
