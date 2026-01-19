import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum as PyEnum

from sqlalchemy import String, ForeignKey, DateTime, Text, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB, JSON
from pgvector.sqlalchemy import Vector

from app.db.base_class import Base


# --- Enums ---
class MessageRole(str, PyEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


# --- Models ---
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    conversations: Mapped[List["Conversation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[List["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    documents: Mapped[List["Document"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )

    role: Mapped[MessageRole] = mapped_column(
        String(50), nullable=False
    )  # Stored as string
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Metadata for citations, token usage, or latency tracking
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class Document(Base):
    """
    Stores uploaded files or knowledge base chunks for RAG.
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(
        String, nullable=False
    )  # S3 URL or local path
    content_snippet: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Text chunk content

    # Stores flexible info like {"page": 1, "chunk_index": 5, "source": "report.pdf"}
    doc_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )

    # Vector Embedding (1536 dims for OpenAI, 768 for HuggingFace/Llama)
    # Ensure you run 'CREATE EXTENSION vector;' in your DB migration!
    embedding: Mapped[Optional[List[float]]] = mapped_column(
        Vector(1536), nullable=True
    )
    # Using compare hash to avoid duplicate uploads
    file_hash: Mapped[Optional[str]] = mapped_column(String(32), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(back_populates="documents")

    # Index for fast similarity search
    __table_args__ = (
        Index(
            "ix_documents_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
