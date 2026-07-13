"""
RAG – Document Ingestion Pipeline

Loads lending policy documents, chunks them, generates embeddings,
and upserts them into the policy_documents table.

Usage:
    python -m app.rag.ingestion
"""

import asyncio
import uuid

from sqlalchemy import delete, text

from app.db.session import init_db, session_context
from app.observability.logging import get_logger
from app.rag.embeddings import get_embedding_service

logger = get_logger(__name__)

# ── Lending Policy Corpus ─────────────────────────────────────────────────────
# In production this would be loaded from S3 / a document store.
# For demo purposes the policies are defined inline.

LENDING_POLICIES: list[dict] = [
    {
        "title": "Debt-to-Income Ratio Policy",
        "content": (
            "The maximum allowable debt-to-income (DTI) ratio for conventional loans "
            "is 43%. For FHA loans the limit is 50%. DTI is calculated as total monthly "
            "debt payments divided by gross monthly income. Applicants with a DTI above "
            "43% require manual underwriting review. Applicants with a DTI above 50% "
            "are automatically declined unless compensating factors are present."
        ),
    },
    {
        "title": "Minimum Credit Score Requirements",
        "content": (
            "Conventional loans require a minimum FICO score of 620. "
            "FHA loans require a minimum FICO score of 580 with 3.5% down or 500 with "
            "10% down. VA loans have no minimum but lenders typically require 580. "
            "Applicants with scores below 580 are declined. Scores between 580-619 "
            "trigger enhanced review. Scores of 740+ qualify for best-rate pricing."
        ),
    },
    {
        "title": "Loan-to-Value and Down Payment Policy",
        "content": (
            "The maximum LTV for conventional purchase loans is 97% (3% down). "
            "PMI is required for LTV above 80%. For investment properties the maximum "
            "LTV is 85%. Jumbo loans (above conforming limits) require a minimum 20% "
            "down payment. Cash-out refinances are capped at 80% LTV."
        ),
    },
    {
        "title": "Income Verification Requirements",
        "content": (
            "All borrowers must provide two years of W-2s or tax returns. "
            "Self-employed borrowers must provide two years of business and personal "
            "returns plus a profit-and-loss statement. Commission income is averaged "
            "over 24 months. Rental income is eligible at 75% of gross rents. "
            "Employment must be verified within 10 business days of closing."
        ),
    },
    {
        "title": "Loan Purpose and Eligible Properties",
        "content": (
            "Eligible loan purposes include primary residence purchase, refinance, "
            "second home, investment property, home equity, auto, personal, and "
            "business expansion. Personal loans above $100,000 require additional "
            "documentation. Business loans require a full business plan and two years "
            "of financial statements. Loans for speculative investment are ineligible."
        ),
    },
    {
        "title": "Compensating Factors Policy",
        "content": (
            "Compensating factors may allow approval for borderline applications. "
            "Acceptable compensating factors include: substantial cash reserves "
            "(≥12 months PITI), low LTV (≤70%), excellent payment history (no lates "
            "in 24 months), significant additional income not used for qualification, "
            "minimal increase in housing expense (<5%). A maximum of two compensating "
            "factors may be used for a DTI up to 50%."
        ),
    },
    {
        "title": "Fair Lending and Anti-Discrimination Policy",
        "content": (
            "All lending decisions must comply with the Equal Credit Opportunity Act "
            "(ECOA), Fair Housing Act (FHA), and Community Reinvestment Act (CRA). "
            "Credit decisions must be based solely on creditworthiness factors. "
            "Protected characteristics including race, color, religion, national origin, "
            "sex, marital status, age, or receipt of public assistance must never "
            "influence lending decisions. All adverse action notices must be provided "
            "within 30 days."
        ),
    },
    {
        "title": "Manual Review Triggers",
        "content": (
            "Applications are escalated to manual underwriting review when: DTI is "
            "between 43%-50%, credit score is between 580-619, the loan amount exceeds "
            "$1,000,000, the property type is non-warrantable condo, there are recent "
            "derogatory events (bankruptcy discharged within 4 years, foreclosure within "
            "7 years), or the applicant has unexplained large deposits in the past 60 days."
        ),
    },
]


def _chunk_text(text: str, max_chars: int = 512) -> list[str]:
    """Simple character-based chunker with sentence boundary awareness."""
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    sentences = text.replace(". ", ".|").split("|")
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) > max_chars:
            if current:
                chunks.append(current.strip())
            current = sentence
        else:
            current += " " + sentence
    if current:
        chunks.append(current.strip())
    return chunks


async def ingest_policies() -> None:
    """
    Full ingestion pipeline:
    1. Clear existing policy documents
    2. Chunk each policy
    3. Generate embeddings in batches
    4. Upsert into policy_documents
    """
    init_db()
    embedder = get_embedding_service()

    async with session_context() as session:
        # Clear existing policies for clean re-ingestion
        await session.execute(delete(text("policy_documents")))  # type: ignore[arg-type]

        all_chunks: list[dict] = []
        for policy in LENDING_POLICIES:
            chunks = _chunk_text(policy["content"])
            for idx, chunk in enumerate(chunks):
                all_chunks.append(
                    {
                        "id": uuid.uuid4(),
                        "title": policy["title"],
                        "content": chunk,
                        "chunk_index": idx,
                    }
                )

        logger.info("ingestion_embedding_start", chunk_count=len(all_chunks))

        # Batch embed
        texts = [c["content"] for c in all_chunks]
        embeddings = await embedder.embed_documents(texts)

        for chunk, embedding in zip(all_chunks, embeddings):
            await session.execute(
                text(
                    """
                    INSERT INTO policy_documents (id, title, content, chunk_index, embedding)
                    VALUES (:id, :title, :content, :chunk_index, CAST(:embedding AS vector))
                    ON CONFLICT DO NOTHING
                    """
                ),
                {
                    "id": str(chunk["id"]),
                    "title": chunk["title"],
                    "content": chunk["content"],
                    "chunk_index": chunk["chunk_index"],
                    "embedding": str(embedding),
                },
            )

        logger.info("ingestion_complete", chunks_inserted=len(all_chunks))


if __name__ == "__main__":
    asyncio.run(ingest_policies())
