
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class Operation(Base):
    __tablename__ = "operations"

    __table_args__ = (
        UniqueConstraint(
            "idempotency_key",
            name="uq_operations_idempotency_key",
        ),
        CheckConstraint(
            "status IN "
            "('in_progress', 'completed', 'failed', "
            "'recovery_required', 'cancelled')",
            name="ck_operations_status",
        ),
        CheckConstraint(
            "attempt_count >= 1",
            name="ck_operations_attempt_count",
        ),
        CheckConstraint(
            """
            (
                status = 'in_progress'
                AND lease_token IS NOT NULL
                AND lease_expires_at IS NOT NULL
            )
            OR
            (
                status <> 'in_progress'
                AND lease_token IS NULL
                AND lease_expires_at IS NULL
            )
            """,
            name="ck_operations_lease_consistency",
        ),
        CheckConstraint(
            "length(trim(idempotency_key)) > 0",
            name="ck_operations_idempotency_key_not_empty",
        ),
        CheckConstraint(
            "length(trim(tool_name)) > 0",
            name="ck_operations_tool_name_not_empty",
        ),
        Index(
            "ix_operations_expired_leases",
            "lease_expires_at",
            postgresql_where=text("status = 'in_progress'"),
        ),
        Index(
            "ix_operations_recovery_queue",
            "updated_at",
            postgresql_where=text("status = 'recovery_required'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    tool_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    arguments_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    result: Mapped[dict | list | str | int | float | bool | None] = (
        mapped_column(JSONB, nullable=True)
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    lease_token: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=True,
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
    )
