"""
Unit Tests – RAG Embeddings

Tests the mock embedding service.
"""

import pytest

from app.rag.embeddings import MockEmbeddingService


class TestMockEmbeddingService:
    """Tests for MockEmbeddingService (no API key required)."""

    @pytest.fixture
    def service(self):
        return MockEmbeddingService()

    async def test_embed_query_returns_correct_dimension(self, service):
        embedding = await service.embed_query("What is the DTI policy?")
        assert len(embedding) == 1536

    async def test_embed_query_is_deterministic(self, service):
        text = "What is the minimum credit score?"
        e1 = await service.embed_query(text)
        e2 = await service.embed_query(text)
        assert e1 == e2

    async def test_different_texts_produce_different_embeddings(self, service):
        e1 = await service.embed_query("DTI policy")
        e2 = await service.embed_query("credit score requirements")
        assert e1 != e2

    async def test_embed_documents_returns_list(self, service):
        texts = ["policy one", "policy two", "policy three"]
        embeddings = await service.embed_documents(texts)
        assert len(embeddings) == 3
        for emb in embeddings:
            assert len(emb) == 1536

    async def test_embed_empty_documents_returns_empty(self, service):
        result = await service.embed_documents([])
        assert result == []
