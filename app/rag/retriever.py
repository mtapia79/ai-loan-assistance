"""
RAG – pgvector Retriever

Performs semantic search against the policy_documents table using
cosine similarity on pgvector embeddings.
"""

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.observability.logging import get_logger
from app.rag.embeddings import EmbeddingService, get_embedding_service

logger = get_logger(__name__)


@dataclass
class RetrievedChunk:
    """A single retrieved policy chunk with its similarity score."""

    id: str
    title: str
    content: str
    similarity: float
    metadata: dict | None = None


class PolicyRetriever:
    """
    Semantic retriever for lending policy documents.

    Uses pgvector cosine similarity to find the most relevant policy
    chunks for a given query.
    """

    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService | None = None,
        top_k: int = 5,
        similarity_threshold: float = 0.70,
    ) -> None:
        self._session = session
        self._embedder = embedding_service or get_embedding_service()
        self._top_k = top_k
        self._threshold = similarity_threshold

    async def retrieve(self, query: str) -> list[RetrievedChunk]:
        """
        Embed the query and return the top-k most similar policy chunks.

        Args:
            query: Natural language question or context to search for.

        Returns:
            List of RetrievedChunk ordered by descending similarity.
        """
        logger.debug("rag_retrieve_start", query_preview=query[:80])
        query_vector = await self._embedder.embed_query(query)

        # pgvector cosine distance: <=> operator (lower = more similar)
        sql = text(
            """
            SELECT
                id::text,
                title,
                content,
                metadata,
                1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM policy_documents
            WHERE 1 - (embedding <=> CAST(:embedding AS vector)) >= :threshold
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
            """
        )

        result = await self._session.execute(
            sql,
            {
                "embedding": str(query_vector),
                "threshold": self._threshold,
                "top_k": self._top_k,
            },
        )

        rows = result.fetchall()
        chunks = [
            RetrievedChunk(
                id=row.id,
                title=row.title,
                content=row.content,
                similarity=float(row.similarity),
                metadata=row.metadata,
            )
            for row in rows
        ]

        logger.info(
            "rag_retrieve_complete",
            query_preview=query[:80],
            chunks_found=len(chunks),
        )
        return chunks

    def format_context(self, chunks: list[RetrievedChunk]) -> str:
        """Format retrieved chunks into a single context string for the LLM."""
        if not chunks:
            return "No relevant policy documents found."
        parts = []
        for i, chunk in enumerate(chunks, 1):
            parts.append(
                f"[Policy {i}: {chunk.title} (similarity: {chunk.similarity:.2f})]\n"
                f"{chunk.content}"
            )
        return "\n\n---\n\n".join(parts)
