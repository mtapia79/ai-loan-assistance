"""
Database – Audit Repository

Repository for AuditLog entity providing audit-specific queries.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog
from app.db.repositories.base import BaseRepository


class AuditRepository(BaseRepository[AuditLog]):
    """Repository for managing AuditLog records."""

    def __init__(self, session: AsyncSession):
        """Initialize audit repository."""
        super().__init__(AuditLog, session)

    async def get_by_application_id(
        self, application_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[AuditLog]:
        """
        Get all audit logs for a specific application.

        Args:
            application_id: The loan application's UUID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of audit logs for the application, ordered by creation time
        """
        stmt = (
            select(self.model)
            .where(self.model.application_id == application_id)
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_agent(
        self, agent_name: str, skip: int = 0, limit: int = 100
    ) -> list[AuditLog]:
        """
        Get all audit logs from a specific agent.

        Args:
            agent_name: Name of the agent
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of audit logs from the agent
        """
        stmt = (
            select(self.model)
            .where(self.model.agent_name == agent_name)
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_trace_id(self, trace_id: str) -> list[AuditLog]:
        """
        Get all audit logs for a specific trace.

        Args:
            trace_id: The OpenTelemetry trace ID

        Returns:
            List of audit logs with the trace ID
        """
        stmt = (
            select(self.model)
            .where(self.model.trace_id == trace_id)
            .order_by(self.model.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def log_action(
        self,
        application_id: UUID,
        agent_name: str,
        action: str,
        details: dict | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
    ) -> AuditLog:
        """
        Create an audit log entry for an action.

        Args:
            application_id: The loan application's UUID
            agent_name: Name of the agent performing the action
            action: Description of the action performed
            details: Additional details about the action
            trace_id: OpenTelemetry trace ID
            span_id: OpenTelemetry span ID

        Returns:
            The created audit log entry
        """
        audit_log = await self.create(
            application_id=application_id,
            agent_name=agent_name,
            action=action,
            details=details,
            trace_id=trace_id,
            span_id=span_id,
        )
        return audit_log

    async def count_by_application_id(self, application_id: UUID) -> int:
        """
        Count audit logs for an application.

        Args:
            application_id: The loan application's UUID

        Returns:
            Count of audit logs
        """
        from sqlalchemy import func

        stmt = (
            select(func.count())
            .select_from(self.model)
            .where(self.model.application_id == application_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0
