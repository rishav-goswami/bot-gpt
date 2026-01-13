import os
import hashlib
from typing import List
from uuid import UUID
from sqlalchemy import select

# LangChain Imports
# from langchain_community.document_loaders import PyPDFLoader
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings

# Database
from app.core.database import AsyncSessionLocal
from app.db.models import Document
from app.core.config import settings
from app.services.socketio_manager import sio


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
        self, doc_id: UUID, file_path: str, conversation_id: UUID
    ):
        print(f"📄 Processing PDF: {file_path}")

        # 1. Calculate File Hash 
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        file_hash = hash_md5.hexdigest()

        async with AsyncSessionLocal() as db:
            # 2. Check for Global Deduplication
            # "Have we ever seen this file before?"
            stmt = select(Document).where(Document.file_hash == file_hash).limit(1)
            result = await db.execute(stmt)
            existing_doc = result.scalars().first()

            if existing_doc:
                print(
                    f"♻️ Cache Hit! File {file_path} (Hash: {file_hash}) processed previously."
                )
                # FETCH all chunks from that previous file
                # (We assume all chunks for a file share the same hash in our schema)
                stmt_all = select(Document).where(Document.file_hash == file_hash)
                existing_chunks_result = await db.execute(stmt_all)
                existing_chunks = existing_chunks_result.scalars().all()

                # COPY existing vectors to new rows for THIS conversation
                # This saves $$$ on OpenAI API calls
                new_chunks = []
                for old_chunk in existing_chunks:
                    new_chunk = Document(
                        conversation_id=conversation_id,
                        filename=os.path.basename(file_path),
                        file_path=file_path,
                        content_snippet=old_chunk.content_snippet,
                        embedding=old_chunk.embedding,  # <--- REUSING VECTOR
                        file_hash=file_hash,
                    )
                    db.add(new_chunk)
                    new_chunks.append(new_chunk)

                await db.commit()
                print(f"✅ Copied {len(new_chunks)} chunks from cache.")

                # Notify Frontend
                await sio.emit_to_room(
                    room=str(conversation_id),
                    event="doc_processed",
                    data={
                        "status": "completed",
                        "chunks": len(new_chunks),
                        "cached": True,
                    },
                )
                return

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

        async with AsyncSessionLocal() as db:
            for text, vector in zip(texts, vectors):
                chunk_doc = Document(
                    conversation_id=conversation_id,
                    filename=os.path.basename(file_path),
                    file_path=file_path,
                    content_snippet=text,
                    embedding=vector,
                    file_hash=file_hash,  # Store hash for future deduplication
                )
                db.add(chunk_doc)

            await db.commit()
            print("✅ Embeddings saved to Postgres.")

        await sio.emit_to_room(
            room=str(conversation_id),
            event="doc_processed",
            data={"status": "completed", "chunks": len(chunks), "cached": False},
        )


rag_service = RAGService()
