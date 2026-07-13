"""Database repositories package."""

from app.db.repositories.audit import AuditRepository
from app.db.repositories.base import BaseRepository
from app.db.repositories.customer import CustomerRepository
from app.db.repositories.loan import LoanRepository
from app.db.repositories.policy import PolicyRepository

__all__ = [
    "BaseRepository",
    "CustomerRepository",
    "LoanRepository",
    "PolicyRepository",
    "AuditRepository",
]
