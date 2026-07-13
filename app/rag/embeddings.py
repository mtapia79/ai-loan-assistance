"""
RAG – Embedding Service

Wraps the OpenAI embedding API with retry logic and batching.
Falls back to a local no-op embedder when the API key is a placeholder
(useful for tests / local dev without a real API key).
"""

from typing import Protocol

from tenacity import retry, stop_after_attempt, wait_exponential

from app.observability.logging import get_logger

logger = get_logger(__name__)


class EmbeddingService(Protocol):
    """Interface contract for any embedding backend."""

    async def embed_query(self, text: str) -> list[float]: ...

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIEmbeddingService:
    """
    Production embedding service backed by OpenAI.

    Uses text-embedding-3-small (1536 dims) by default.
    """

    def __init__(self) -> None:
        from app.config import get_settings

        self._settings = get_settings()
        self._client: object | None = None

    def _get_client(self):  # type: ignore[return]
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=self._settings.openai_api_key)
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def embed_query(self, text: str) -> list[float]:
        client = self._get_client()
        response = await client.embeddings.create(
            model=self._settings.openai_embedding_model,
            input=text,
        )
        return response.data[0].embedding

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        client = self._get_client()
        response = await client.embeddings.create(
            model=self._settings.openai_embedding_model,
            input=texts,
        )
        return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]


class MockEmbeddingService:
    """
    Deterministic mock embedding service for local dev and tests.

    Returns a zero vector of the configured dimension so no API key is needed.
    """

    def __init__(self) -> None:
        from app.config import get_settings

        self._dim = get_settings().vector_dimension

    async def embed_query(self, text: str) -> list[float]:
        # Deterministic hash-based embedding for testability
        import hashlib

        seed = int(hashlib.sha256(text.encode()).hexdigest(), 16)
        import random

        rng = random.Random(seed)
        return [rng.gauss(0, 1) for _ in range(self._dim)]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [await self.embed_query(t) for t in texts]


def get_embedding_service() -> EmbeddingService:
    """Factory: return appropriate embedding service based on config."""
    from app.config import get_settings

    settings = get_settings()
    if settings.openai_api_key == "sk-placeholder":
        logger.warning("embedding_service_mock", reason="No real API key configured")
        return MockEmbeddingService()
    return OpenAIEmbeddingService()
