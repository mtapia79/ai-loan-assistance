"""
Unit Tests – Configuration

Tests settings loading and validation.
"""

import pytest
from pydantic import ValidationError

from app.config import Settings


class TestSettings:
    """Tests for the Settings configuration class."""

    def test_default_settings_load(self):
        s = Settings()
        assert s.app_env == "development"
        assert s.app_name == "AI Loan Assistant"
        assert s.vector_dimension == 1536

    def test_database_url_computed(self):
        s = Settings(
            postgres_host="db-host",
            postgres_port=5432,
            postgres_db="testdb",
            postgres_user="testuser",
            postgres_password="testpass",
        )
        url = s.database_url
        assert "testuser" in url
        assert "testpass" in url
        assert "db-host" in url
        assert "testdb" in url
        assert "asyncpg" in url

    def test_sync_database_url_uses_psycopg2(self):
        s = Settings()
        assert "psycopg2" in s.database_url_sync

    def test_production_requires_real_jwt_secret(self):
        with pytest.raises(ValidationError):
            Settings(
                app_env="production",
                jwt_secret_key="dev-secret-key-change-in-production",
                openai_api_key="sk-real-key",
            )

    def test_production_requires_real_openai_key(self):
        with pytest.raises(ValidationError):
            Settings(
                app_env="production",
                jwt_secret_key="a-real-secret-key-that-is-long-enough",
                openai_api_key="sk-placeholder",
            )

    def test_development_allows_placeholder_keys(self):
        # Should not raise
        s = Settings(
            app_env="development",
            jwt_secret_key="dev-secret-key-change-in-production",
            openai_api_key="sk-placeholder",
        )
        assert s.app_env == "development"
