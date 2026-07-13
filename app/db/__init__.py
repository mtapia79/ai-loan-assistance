"""app/db package."""

from app.db.models import Base, Customer, LoanApplication, LoanDocument, PolicyDocument, AuditLog
from app.db.repositories import (
    BaseRepository,
    CustomerRepository,
    LoanRepository,
    PolicyRepository,
    AuditRepository,
)
from app.db.session import get_session, init_db, close_db, session_context
from app.db.unit_of_work import UnitOfWork

__all__ = [
    # Models
    "Base",
    "Customer",
    "LoanApplication",
    "LoanDocument",
    "PolicyDocument",
    "AuditLog",
    # Repositories
    "BaseRepository",
    "CustomerRepository",
    "LoanRepository",
    "PolicyRepository",
    "AuditRepository",
    # Session management
    "get_session",
    "init_db",
    "close_db",
    "session_context",
    # Unit of Work
    "UnitOfWork",
]

