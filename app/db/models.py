"""
Database – ORM Models

Defines all SQLAlchemy models including pgvector-backed policy embeddings
and audit-ready loan application records.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.config import get_settings


class Base(DeclarativeBase):
    pass


# ── Loan Application ─────────────────────────────────────────────────────────


class LoanApplication(Base):
    """Core loan application record with full audit trail."""

    __tablename__ = "loan_applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    applicant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    applicant_email: Mapped[str] = mapped_column(String(255), nullable=False)

    # Financial data
    annual_income: Mapped[float] = mapped_column(Float, nullable=False)
    monthly_debt: Mapped[float] = mapped_column(Float, nullable=False)
    requested_amount: Mapped[float] = mapped_column(Float, nullable=False)
    loan_purpose: Mapped[str] = mapped_column(String(100), nullable=False)
    credit_score: Mapped[int | None] = mapped_column(nullable=True)

    # Decision
    recommendation: Mapped[str | None] = mapped_column(
        Enum("APPROVE", "REJECT", "MANUAL_REVIEW", name="recommendation_enum"),
        nullable=True,
    )
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_reasoning: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        Enum("PENDING", "PROCESSING", "COMPLETED", "FAILED", name="application_status_enum"),
        default="PENDING",
        nullable=False,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    documents: Mapped[list["LoanDocument"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_loan_applications_status", "status"),
        Index("ix_loan_applications_created_at", "created_at"),
    )


# ── Loan Documents ────────────────────────────────────────────────────────────


class LoanDocument(Base):
    """Uploaded financial document metadata."""

    __tablename__ = "loan_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("loan_applications.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    s3_key: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    application: Mapped["LoanApplication"] = relationship(back_populates="documents")


# ── Policy Embeddings (RAG) ───────────────────────────────────────────────────


class PolicyDocument(Base):
    """Lending policy chunks stored with pgvector embeddings for RAG."""

    __tablename__ = "policy_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(nullable=False, default=0)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    # pgvector column – dimension set from config
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(get_settings().vector_dimension), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index(
            "ix_policy_documents_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


# ── Audit Log ─────────────────────────────────────────────────────────────────


class AuditLog(Base):
    """Immutable audit trail for all agent decisions and actions."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("loan_applications.id", ondelete="CASCADE"), nullable=False
    )
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(200), nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    span_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    application: Mapped["LoanApplication"] = relationship(back_populates="audit_logs")

    __table_args__ = (
        Index("ix_audit_logs_application_id", "application_id"),
        Index("ix_audit_logs_created_at", "created_at"),
    )
