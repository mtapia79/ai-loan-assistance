"""
Database – Customer Repository

Repository for Customer entity providing customer-specific queries.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Customer
from app.db.repositories.base import BaseRepository


class CustomerRepository(BaseRepository[Customer]):
    """Repository for managing Customer records."""

    def __init__(self, session: AsyncSession):
        """Initialize customer repository."""
        super().__init__(Customer, session)

    async def get_by_email(self, email: str) -> Customer | None:
        """
        Get customer by email address.

        Args:
            email: The customer's email address

        Returns:
            Customer instance or None if not found
        """
        stmt = select(self.model).where(self.model.email == email)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_verified_customers(self, skip: int = 0, limit: int = 100) -> list[Customer]:
        """
        Get all verified customers.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of verified customers
        """
        stmt = (
            select(self.model)
            .where(self.model.kyc_status == "VERIFIED")
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_pending_kyc(self, skip: int = 0, limit: int = 100) -> list[Customer]:
        """
        Get customers with pending KYC verification.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of customers with pending KYC
        """
        stmt = (
            select(self.model)
            .where(self.model.kyc_status == "PENDING")
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def email_exists(self, email: str) -> bool:
        """
        Check if email is already registered.

        Args:
            email: Email address to check

        Returns:
            True if email exists, False otherwise
        """
        stmt = select(self.model).where(self.model.email == email)
        result = await self.session.execute(stmt)
        return result.scalars().first() is not None
