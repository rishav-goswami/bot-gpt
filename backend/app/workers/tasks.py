import asyncio
from uuid import UUID
from app.core.celery_app import celery_app
from app.services.rag_service import rag_service


# Helper to run async code in sync Celery worker
def run_async(coroutine):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coroutine)


@celery_app.task(name="ingest_pdf")
def ingest_pdf_task(doc_id_str: str, file_path: str, conversation_id_str: str):
    """
    Celery task to ingest a PDF.
    Wraps the async RAGService logic.
    """
    doc_id = UUID(doc_id_str)
    conversation_id = UUID(conversation_id_str)

    # We create a new event loop for this thread to run the async DB/LLM logic
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            rag_service.process_document(doc_id, file_path, conversation_id)
        )
    finally:
        loop.close()

    return f"Processed {file_path}"
