from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


# --- Enums (Matching DB) ---
class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


# --- Shared Properties ---
class MessageBase(BaseModel):
    role: MessageRole
    content: str
    metadata_: Optional[Dict[str, Any]] = Field(default=None, alias="metadata")


# --- Message Schemas ---
class MessageCreate(BaseModel):
    """Payload to send a new message"""

    content: str = Field(..., min_length=1, description="The message text")
    # Role is usually 'user' by default in the API endpoint logic,
    # but we allow it here if needed (e.g. for system prompts).
    role: MessageRole = MessageRole.USER


class MessageResponse(MessageBase):
    id: UUID
    conversation_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# --- Conversation Schemas ---
class ChatCreate(BaseModel):
    """Payload to start a conversation"""

    first_message: str = Field(..., min_length=1, example="Hello, how does RAG work?")
    # Optional: Attach a document ID immediately if 'Chat with PDF'
    document_id: Optional[UUID] = None


class ConversationBase(BaseModel):
    title: Optional[str] = None


class ConversationSummary(ConversationBase):
    """Lightweight view for the sidebar list (no messages)"""

    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationDetail(ConversationSummary):
    """Full view for the chat window (includes messages)"""

    messages: List[MessageResponse] = []
    # We will add documents here too so the UI knows what context is loaded
    # documents: List[DocumentResponse] = [] (We'll add this after defining Document schema)

    model_config = ConfigDict(from_attributes=True)
