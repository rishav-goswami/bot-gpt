import shutil
import os
from typing import Any, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from app.workers.tasks import ingest_pdf_task

from app.api import deps
from app import schemas
from app import crud

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/", response_model=schemas.DocumentResponse, status_code=201)
async def upload_document(
    conversation_id: UUID = Form(...),  # Passed as form data
    file: UploadFile = File(...),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Upload a PDF, save to disk, and link to conversation.
    Triggers RAG ingestion (Embeddings) in background.
    """
    # 1. Validate File
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

    # 2. Save File Locally
    file_path = os.path.join(UPLOAD_DIR, f"{conversation_id}_{file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 3. Create DB Entry
    doc_in = schemas.DocumentCreate(
        filename=file.filename,
        file_path=file_path,
        conversation_id=conversation_id,
        content_snippet="Processing...",  # Placeholder until worker runs
    )
    doc = await crud.document.create(db=db, obj_in=doc_in)

    # 4. Trigger Background Task (Celery)
    ingest_pdf_task.delay(str(doc.id), file_path, str(conversation_id))
    print(f"Triggered ingestion for doc {doc.id} at {file_path}")

    return doc


@router.get("/{conversation_id}", response_model=List[schemas.DocumentResponse])
async def list_documents(
    conversation_id: UUID, db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """List all documents attached to a conversation."""
    return await crud.document.get_by_conversation(db, conversation_id)
