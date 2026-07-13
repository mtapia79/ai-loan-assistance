"""
Database – Base Repository

Generic base repository class implementing common CRUD operations.
All repositories inherit from this and add domain-specific methods.
"""

from typing import Generic, TypeVar, Any
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

ModelT = TypeVar("ModelT", bound=DeclarativeBase)


class BaseRepository(Generic[ModelT]):
    """
    Generic repository providing common CRUD operations.

    Type Parameters:
        ModelT: The SQLAlchemy model type this repository manages.

    Usage:
        class UserRepository(BaseRepository[User]):
            pass

        user_repo = UserRepository(User, session)
        user = await user_repo.get_by_id(user_id)
    """

    def __init__(self, model: type[ModelT], session: AsyncSession):
        """
        Initialize repository.

        Args:
            model: The SQLAlchemy model class
            session: The async database session
        """
        self.model = model
        self.session = session

    async def get_by_id(self, id_: UUID | str | int) -> ModelT | None:
        """
        Get a record by ID.

        Args:
            id_: The primary key value

        Returns:
            The model instance or None if not found
        """
        return await self.session.get(self.model, id_)

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[ModelT]:
        """
        Get all records with pagination.

        Args:
            skip: Number of records to skip (offset)
            limit: Maximum number of records to return

        Returns:
            List of model instances
        """
        stmt = select(self.model).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count(self) -> int:
        """
        Count total records.

        Returns:
            Total count of records
        """
        stmt = select(func.count()).select_from(self.model)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def create(self, **kwargs: Any) -> ModelT:
        """
        Create and return a new record.

        Args:
            **kwargs: Attributes to set on the model

        Returns:
            The newly created model instance
        """
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()  # Get the ID without committing
        return instance

    async def update(self, id_: UUID | str | int, **kwargs: Any) -> ModelT | None:
        """
        Update a record by ID.

        Args:
            id_: The primary key value
            **kwargs: Attributes to update

        Returns:
            The updated model instance or None if not found
        """
        instance = await self.get_by_id(id_)
        if instance:
            for key, value in kwargs.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)
            await self.session.flush()
        return instance

    async def delete(self, id_: UUID | str | int) -> bool:
        """
        Delete a record by ID.

        Args:
            id_: The primary key value

        Returns:
            True if deleted, False if not found
        """
        instance = await self.get_by_id(id_)
        if instance:
            await self.session.delete(instance)
            await self.session.flush()
            return True
        return False

    async def exists(self, id_: UUID | str | int) -> bool:
        """
        Check if a record exists.

        Args:
            id_: The primary key value

        Returns:
            True if record exists, False otherwise
        """
        return await self.get_by_id(id_) is not None
