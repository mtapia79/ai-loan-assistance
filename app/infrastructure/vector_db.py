"""
Infrastructure – Vector Database Connection Manager

Manages pgvector connections for vector embeddings storage and retrieval.
Provides high-level vector operations with async support.
"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.observability.logging import get_logger

logger = get_logger(__name__)


class VectorDatabase:
    """
    Wrapper around pgvector operations.

    All methods are async-compatible and designed to work with
    SQLAlchemy async sessions.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize vector database wrapper.

        Args:
            session: SQLAlchemy async session for database operations.
        """
        self.session = session

    async def ensure_extension(self) -> None:
        """Ensure pgvector extension is installed."""
        try:
            await self.session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            logger.info("pgvector_extension_ensured")
        except Exception as exc:
            logger.error("pgvector_extension_error", error=str(exc))
            raise

    async def create_vector_table(
        self,
        table_name: str,
        vector_dimension: int = 1536,
    ) -> None:
        """
        Create a vector storage table if it doesn't exist.

        Args:
            table_name: Name of the table to create.
            vector_dimension: Dimension of the vector column (default 1536 for OpenAI embeddings).
        """
        try:
            sql = f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                embedding vector({vector_dimension}) NOT NULL,
                metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS {table_name}_embedding_idx
                ON {table_name}
                USING HNSW (embedding vector_cosine_ops);
            """
            await self.session.execute(text(sql))
            await self.session.commit()
            logger.info("vector_table_created", table_name=table_name)
        except Exception as exc:
            logger.error("vector_table_creation_error", error=str(exc), table=table_name)
            raise

    async def insert_vector(
        self,
        table_name: str,
        content: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """
        Insert a vector record.

        Args:
            table_name: Table to insert into.
            content: Text content to store.
            embedding: Vector embedding (list of floats).
            metadata: Optional metadata as dict.

        Returns:
            ID of inserted record.
        """
        try:
            sql = f"""
            INSERT INTO {table_name} (content, embedding, metadata)
            VALUES (:content, :embedding, :metadata)
            RETURNING id;
            """
            result = await self.session.execute(
                text(sql),
                {
                    "content": content,
                    "embedding": embedding,
                    "metadata": metadata or {},
                },
            )
            record_id = result.scalar()
            await self.session.commit()
            return record_id
        except Exception as exc:
            logger.error("vector_insert_error", error=str(exc), table=table_name)
            raise

    async def search_similar(
        self,
        table_name: str,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Search for vectors similar to query embedding using cosine similarity.

        Args:
            table_name: Table to search in.
            query_embedding: Query vector (list of floats).
            top_k: Number of results to return.

        Returns:
            List of similar records sorted by similarity (highest first).
        """
        try:
            sql = f"""
            SELECT id, content, metadata, (1 - (embedding <=> :query_embedding)) as similarity
            FROM {table_name}
            ORDER BY embedding <=> :query_embedding
            LIMIT :top_k;
            """
            result = await self.session.execute(
                text(sql),
                {
                    "query_embedding": query_embedding,
                    "top_k": top_k,
                },
            )
            rows = result.fetchall()
            return [
                {
                    "id": row[0],
                    "content": row[1],
                    "metadata": row[2] or {},
                    "similarity": float(row[3]),
                }
                for row in rows
            ]
        except Exception as exc:
            logger.error("vector_search_error", error=str(exc), table=table_name)
            raise

    async def health_check(self) -> dict[str, str]:
        """
        Check vector database health.

        Returns:
            dict with status "ok" or error message.
        """
        try:
            result = await self.session.execute(text("SELECT 1"))
            if result.scalar() == 1:
                return {"vector_db": "ok"}
            return {"vector_db": "error: query failed"}
        except Exception as exc:
            return {"vector_db": f"error: {exc}"}
