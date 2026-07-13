"""
Database – Unit of Work

Implements the Unit of Work pattern for transaction management.
Manages all repositories and coordinates database operations.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import (
    AuditRepository,
    CustomerRepository,
    LoanRepository,
    PolicyRepository,
)


class UnitOfWork:
    """
    Unit of Work pattern implementation for coordinating repository operations.

    Manages all repositories and provides transaction semantics (commit/rollback).

    Usage:
        async with UnitOfWork(session) as uow:
            customer = await uow.customers.get_by_email("user@example.com")
            loan = await uow.loans.create(customer_id=customer.id, ...)
            await uow.commit()

    Attributes:
        customers: CustomerRepository instance
        loans: LoanRepository instance
        policies: PolicyRepository instance
        audits: AuditRepository instance
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize Unit of Work.

        Args:
            session: The async database session
        """
        self._session = session
        self.customers = CustomerRepository(session)
        self.loans = LoanRepository(session)
        self.policies = PolicyRepository(session)
        self.audits = AuditRepository(session)

    async def commit(self) -> None:
        """
        Commit all changes to the database.

        Raises:
            Exception: If commit fails, all changes are rolled back
        """
        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

    async def rollback(self) -> None:
        """Rollback all changes since last commit."""
        await self._session.rollback()

    async def __aenter__(self) -> "UnitOfWork":
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type: type | None, exc_val: Exception | None, exc_tb: object | None) -> None:
        """
        Exit async context manager.

        Args:
            exc_type: Exception type if an error occurred
            exc_val: Exception value if an error occurred
            exc_tb: Exception traceback if an error occurred
        """
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()
        await self._session.close()
