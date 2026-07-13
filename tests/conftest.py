"""
Test Configuration

Provides shared fixtures for API testing, mock LLMs, and in-memory DB.
"""

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_session, init_db
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Initialize database before running tests."""
    init_db()
    yield


@pytest.fixture(scope="session")
def settings():
    return get_settings()


@pytest.fixture
def client():
    """Synchronous test client (for simple non-async tests)."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
async def async_client():
    """Async test client for full async route testing."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as c:
        yield c


@pytest.fixture
async def db() -> AsyncSession:
    """Database session for tests."""
    async for session in get_session():
        yield session


@pytest.fixture
def sample_loan_request() -> dict:
    """A valid loan application payload for testing."""
    return {
        "applicant_name": "Jane Doe",
        "applicant_email": "jane.doe@example.com",
        "annual_income": 95000.00,
        "monthly_debt": 1200.00,
        "requested_amount": 350000.00,
        "loan_purpose": "home_purchase",
        "credit_score": 740,
    }


@pytest.fixture
def high_risk_loan_request() -> dict:
    """A high-risk loan application payload."""
    return {
        "applicant_name": "John Risk",
        "applicant_email": "john.risk@example.com",
        "annual_income": 40000.00,
        "monthly_debt": 2500.00,
        "requested_amount": 500000.00,
        "loan_purpose": "personal",
        "credit_score": 550,
    }
