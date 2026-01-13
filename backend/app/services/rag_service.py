
import os
from typing import List
from uuid import UUID

# LangChain Imports
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings

# Database
from app.core.database import AsyncSessionLocal
from app.db.models import Document
from app.core.config import settings
from app.services.socket_manager import sio # To notify user when done

class RAGService:
    def __init__(self):
        # Initialize Embedding Model
        # If OPENAI_API_KEY is present, use it (Best for production)
        if settings.OPENAI_API_KEY:
            self.embeddings = OpenAIEmbeddings(
                model=settings.EMBEDDING_MODEL,
                openai_api_key=settings.OPENAI_API_KEY
            )
        else:
            # Fallback to local CPU model (Free, good for the assessment)
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )

    async def process_document(self, doc_id: UUID, file_path: str, conversation_id: UUID):
        """
        1. Load PDF
        2. Split into chunks
        3. Embed chunks
        4. Save to DB (pgvector)
        """
        print(f"📄 Processing PDF: {file_path}")
        
        # 1. Load PDF
        loader = PyPDFLoader(file_path)
        pages = loader.load()
        
        # 2. Split Text
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""]
        )
        chunks = text_splitter.split_documents(pages)
        print(f"🧩 Split into {len(chunks)} chunks.")

        # 3. Generate Embeddings (Batch)
        texts = [c.page_content for c in chunks]
        vectors = self.embeddings.embed_documents(texts)

        # 4. Save Chunks to Postgres
        async with AsyncSessionLocal() as db:
            # Create a new Document row for EACH chunk
            # (In a real app, you might have a parent Document and child DocumentChunks,
            # but for this assessment, multiple Document rows works perfectly)
            for i, (text, vector) in enumerate(zip(texts, vectors)):
                chunk_doc = Document(
                    conversation_id=conversation_id,
                    filename=os.path.basename(file_path),
                    file_path=file_path,
                    content_snippet=text, # Store the actual text for retrieval
                    embedding=vector      # Store the vector
                )
                db.add(chunk_doc)
            
            await db.commit()
            print("✅ Embeddings saved to Postgres.")

        # 5. Notify Frontend via Socket.IO
        await sio.emit_to_room(
            room=str(conversation_id),
            event="doc_processed",
            data={"status": "completed", "chunks": len(chunks)}
        )

rag_service = RAGService()