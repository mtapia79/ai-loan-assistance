"""Create initial schema with all models.

Revision ID: 001_create_initial_schema
Revises:
Create Date: 2026-07-13 12:57:46.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "001_create_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # Create customers table
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("phone_number", sa.String(20), nullable=True),
        sa.Column("date_of_birth", sa.DateTime(timezone=True), nullable=True),
        sa.Column("street_address", sa.String(255), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(50), nullable=True),
        sa.Column("postal_code", sa.String(20), nullable=True),
        sa.Column("country", sa.String(100), nullable=False),
        sa.Column(
            "kyc_status",
            postgresql.ENUM("PENDING", "VERIFIED", "REJECTED", name="kyc_status_enum"),
            nullable=False,
        ),
        sa.Column("kyc_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("annual_income", sa.Float(), nullable=True),
        sa.Column("credit_score", sa.Integer(), nullable=True),
        sa.Column("employment_status", sa.String(50), nullable=True),
        sa.Column("employment_industry", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_customers_email", "customers", ["email"], unique=False)
    op.create_index("ix_customers_kyc_status", "customers", ["kyc_status"], unique=False)
    op.create_index("ix_customers_created_at", "customers", ["created_at"], unique=False)

    # Create loan_applications table
    op.create_table(
        "loan_applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("applicant_name", sa.String(255), nullable=False),
        sa.Column("applicant_email", sa.String(255), nullable=False),
        sa.Column("annual_income", sa.Float(), nullable=False),
        sa.Column("monthly_debt", sa.Float(), nullable=False),
        sa.Column("requested_amount", sa.Float(), nullable=False),
        sa.Column("loan_purpose", sa.String(100), nullable=False),
        sa.Column("credit_score", sa.Integer(), nullable=True),
        sa.Column(
            "recommendation",
            postgresql.ENUM(
                "APPROVE", "REJECT", "MANUAL_REVIEW", name="recommendation_enum"
            ),
            nullable=True,
        ),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("agent_reasoning", postgresql.JSON(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING", "PROCESSING", "COMPLETED", "FAILED", name="application_status_enum"
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_loan_applications_status", "loan_applications", ["status"], unique=False
    )
    op.create_index(
        "ix_loan_applications_created_at", "loan_applications", ["created_at"], unique=False
    )
    op.create_index(
        "ix_loan_applications_customer_id", "loan_applications", ["customer_id"], unique=False
    )

    # Create loan_documents table
    op.create_table(
        "loan_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("document_type", sa.String(100), nullable=False),
        sa.Column("s3_key", sa.String(1000), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("extracted_data", postgresql.JSON(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["loan_applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create policy_documents table
    op.create_table(
        "policy_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("metadata", postgresql.JSON(), nullable=True),
        sa.Column("embedding", sa.dialects.postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("action", sa.String(200), nullable=False),
        sa.Column("details", postgresql.JSON(), nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("span_id", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["loan_applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_application_id", "audit_logs", ["application_id"], unique=False)
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("audit_logs")
    op.drop_table("policy_documents")
    op.drop_table("loan_documents")
    op.drop_table("loan_applications")
    op.drop_table("customers")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS application_status_enum")
    op.execute("DROP TYPE IF EXISTS recommendation_enum")
    op.execute("DROP TYPE IF EXISTS kyc_status_enum")
