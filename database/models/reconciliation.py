
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class OperationReconciliation(Base):
    __tablename__ = "operation_reconciliations"

    __table_args__ = (
        CheckConstraint(
            "decision IN ('completed', 'failed')",
            name="ck_reconciliation_decision",
        ),
        CheckConstraint(
            "length(trim(evidence)) > 0",
            name="ck_reconciliation_evidence_not_empty",
        ),
        CheckConstraint(
            "length(trim(reconciled_by)) > 0",
            name="ck_reconciliation_reconciled_by_not_empty",
        ),
        Index(
            "ix_reconciliations_operation_history",
            "operation_id",
            "reconciled_at",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    operation_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "operations.id",
            name="fk_reconciliations_operation_id_operations",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    decision: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    evidence: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    reconciled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    reconciled_by: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    previous_result: Mapped[dict | list | str | int | float | bool | None] = (
        mapped_column(JSONB, nullable=True)
    )

    reconciled_result: Mapped[dict | list | str | int | float | bool | None] = (
        mapped_column(JSONB, nullable=True)
    )
