from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class DocumentBase(BaseModel):
    filename: str
    file_path: str


class DocumentCreate(DocumentBase):
    """Internal schema used when saving to DB"""

    conversation_id: Optional[UUID] = None
    content_snippet: Optional[str] = None
    # We don't validate 'embedding' here as it's handled internally


class DocumentResponse(DocumentBase):
    id: UUID
    created_at: datetime
    conversation_id: Optional[UUID] = None

    # We might want to return a snippet to show the user "This is what I read"
    content_snippet: Optional[str] = Field(
        default=None, description="First 100 chars preview"
    )
    
    # Include embedding status (null means not processed yet)
    embedding: Optional[List[float]] = Field(
        default=None, description="Vector embedding (null if not processed)"
    )

    model_config = ConfigDict(from_attributes=True)
