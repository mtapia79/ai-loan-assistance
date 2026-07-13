"""
Database – Policy Repository

Repository for PolicyDocument entity providing policy-specific queries with vector search.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PolicyDocument
from app.db.repositories.base import BaseRepository


class PolicyRepository(BaseRepository[PolicyDocument]):
    """Repository for managing PolicyDocument records with RAG support."""

    def __init__(self, session: AsyncSession):
        """Initialize policy repository."""
        super().__init__(PolicyDocument, session)

    async def get_by_title(self, title: str) -> list[PolicyDocument]:
        """
        Get policy documents by title (partial match).

        Args:
            title: The policy title to search for

        Returns:
            List of matching policy documents
        """
        stmt = select(self.model).where(self.model.title.ilike(f"%{title}%"))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_all_active(self, skip: int = 0, limit: int = 100) -> list[PolicyDocument]:
        """
        Get all active policy documents (those with embeddings).

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of active policy documents with embeddings
        """
        stmt = (
            select(self.model)
            .where(self.model.embedding.is_not(None))
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_active(self) -> int:
        """
        Count policy documents with embeddings.

        Returns:
            Count of active policies
        """
        stmt = select(self.model).where(self.model.embedding.is_not(None))
        result = await self.session.execute(stmt)
        return len(result.scalars().all())

    async def get_by_content_fragment(self, fragment: str, skip: int = 0, limit: int = 100) -> list[PolicyDocument]:
        """
        Get policy documents by content fragment (keyword search).

        Args:
            fragment: Text fragment to search for
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of matching documents
        """
        stmt = (
            select(self.model)
            .where(self.model.content.ilike(f"%{fragment}%"))
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def vector_search(
        self, embedding: list[float], limit: int = 5
    ) -> list[PolicyDocument]:
        """
        Search for similar policies using vector similarity (cosine distance).

        Args:
            embedding: Query embedding vector
            limit: Maximum number of results to return

        Returns:
            List of most similar policy documents, ordered by similarity
        """
        # Use raw SQL for vector similarity search with pgvector
        from sqlalchemy import text

        # Convert embedding to pgvector format
        embedding_str = "[" + ",".join(str(e) for e in embedding) + "]"

        sql = text(
            f"""
            SELECT id, title, content, chunk_index, metadata, embedding, created_at
            FROM policy_documents
            WHERE embedding IS NOT NULL
            ORDER BY embedding <-> '{embedding_str}'::vector
            LIMIT :limit
            """
        )

        result = await self.session.execute(sql)
        rows = result.fetchall()

        # Fetch the full model instances
        ids = [row[0] for row in rows]
        if not ids:
            return []

        stmt = select(self.model).where(self.model.id.in_(ids))
        result = await self.session.execute(stmt)
        return result.scalars().all()
