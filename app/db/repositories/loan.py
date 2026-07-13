"""
Database – Loan Repository

Repository for LoanApplication entity providing loan-specific queries.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LoanApplication
from app.db.repositories.base import BaseRepository


class LoanRepository(BaseRepository[LoanApplication]):
    """Repository for managing LoanApplication records."""

    def __init__(self, session: AsyncSession):
        """Initialize loan repository."""
        super().__init__(LoanApplication, session)

    async def get_by_customer_id(
        self, customer_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[LoanApplication]:
        """
        Get all loan applications for a customer.

        Args:
            customer_id: The customer's UUID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of loan applications for the customer
        """
        stmt = (
            select(self.model)
            .where(self.model.customer_id == customer_id)
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_status(
        self, status: str, skip: int = 0, limit: int = 100
    ) -> list[LoanApplication]:
        """
        Get loan applications by status.

        Args:
            status: The application status (PENDING, PROCESSING, COMPLETED, FAILED)
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of applications with the specified status
        """
        stmt = select(self.model).where(self.model.status == status).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_pending_applications(
        self, skip: int = 0, limit: int = 100
    ) -> list[LoanApplication]:
        """
        Get all pending loan applications.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of pending applications
        """
        return await self.get_by_status("PENDING", skip, limit)

    async def get_by_recommendation(
        self, recommendation: str, skip: int = 0, limit: int = 100
    ) -> list[LoanApplication]:
        """
        Get loan applications by recommendation.

        Args:
            recommendation: The recommendation type (APPROVE, REJECT, MANUAL_REVIEW)
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of applications with the specified recommendation
        """
        stmt = (
            select(self.model)
            .where(self.model.recommendation == recommendation)
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_approved_applications(
        self, skip: int = 0, limit: int = 100
    ) -> list[LoanApplication]:
        """
        Get all approved loan applications.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of approved applications
        """
        return await self.get_by_recommendation("APPROVE", skip, limit)

    async def get_rejected_applications(
        self, skip: int = 0, limit: int = 100
    ) -> list[LoanApplication]:
        """
        Get all rejected loan applications.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of rejected applications
        """
        return await self.get_by_recommendation("REJECT", skip, limit)

    async def get_manual_review_applications(
        self, skip: int = 0, limit: int = 100
    ) -> list[LoanApplication]:
        """
        Get all manual review loan applications.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of manual review applications
        """
        return await self.get_by_recommendation("MANUAL_REVIEW", skip, limit)
