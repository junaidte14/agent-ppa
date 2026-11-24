
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from database.models import Operation, OperationReconciliation


class IdempotencyRepository:
    """
    PostgreSQL data-access layer for idempotent operations.

    The caller owns the SQLAlchemy session and transaction.
    This repository never commits, rolls back, or closes sessions.
    """

    @staticmethod
    def get_by_idempotency_key(
        session: Session,
        idempotency_key: str,
    ) -> Operation | None:
        statement = select(Operation).where(
            Operation.idempotency_key == idempotency_key
        )
        return session.scalar(statement)

    @staticmethod
    def lookup(
        session: Session,
        idempotency_key: str,
        tool_name: str | None = None,
        arguments_hash: str | None = None,
    ) -> dict[str, Any] | None:
        operation = IdempotencyRepository.get_by_idempotency_key(
            session,
            idempotency_key,
        )

        if operation is None:
            return None

        if (
            tool_name is not None
            and arguments_hash is not None
            and (
                operation.tool_name != tool_name
                or operation.arguments_hash != arguments_hash
            )
        ):
            return {
                "status": "conflict",
                "result": None,
            }

        return {
            "status": operation.status,
            "result": operation.result,
        }

    @staticmethod
    def claim(
        session: Session,
        idempotency_key: str,
        tool_name: str,
        arguments_hash: str,
        lease_duration_seconds: int,
    ) -> dict[str, Any]:
        """
        Atomically claim an operation.

        PostgreSQL's unique constraint and ON CONFLICT handling
        ensure that only one concurrent request creates the operation.
        """

        lease_token = uuid4()

        lease_expiry = (
            func.now()
            + text(
                "(:lease_duration_seconds * INTERVAL '1 second')"
            ).bindparams(
                lease_duration_seconds=lease_duration_seconds
            )
        )

        statement = (
            pg_insert(Operation)
            .values(
                idempotency_key=idempotency_key,
                tool_name=tool_name,
                arguments_hash=arguments_hash,
                status="in_progress",
                lease_token=lease_token,
                lease_expires_at=lease_expiry,
                attempt_count=1,
            )
            .on_conflict_do_nothing(
                index_elements=[Operation.idempotency_key]
            )
            .returning(Operation.id)
        )

        inserted_id = session.scalar(statement)

        if inserted_id is not None:
            return {
                "status": "new",
                "result": None,
                "lease_token": str(lease_token),
            }

        existing = IdempotencyRepository.get_by_idempotency_key(
            session,
            idempotency_key,
        )

        if existing is None:
            raise RuntimeError(
                "Operation could not be claimed or retrieved."
            )

        if (
            existing.tool_name != tool_name
            or existing.arguments_hash != arguments_hash
        ):
            return {
                "status": "conflict",
                "result": None,
                "lease_token": None,
            }

        return {
            "status": existing.status,
            "result": existing.result,
            "lease_token": None,
        }

    @staticmethod
    def finish(
        session: Session,
        idempotency_key: str,
        lease_token: str | UUID,
        result: Any,
        status: str = "completed",
    ) -> bool:
        token = UUID(str(lease_token))

        statement = (
            update(Operation)
            .where(
                Operation.idempotency_key == idempotency_key,
                Operation.lease_token == token,
                Operation.status == "in_progress",
                Operation.lease_expires_at > func.now(),
            )
            .values(
                status=status,
                result=result,
                lease_token=None,
                lease_expires_at=None,
                updated_at=func.now(),
            )
            .returning(Operation.id)
        )

        return session.scalar(statement) is not None

    @staticmethod
    def renew_lease(
        session: Session,
        idempotency_key: str,
        lease_token: str | UUID,
        lease_duration_seconds: int,
    ) -> bool:
        token = UUID(str(lease_token))

        new_expiry = (
            func.now()
            + text(
                "(:lease_duration_seconds * INTERVAL '1 second')"
            ).bindparams(
                lease_duration_seconds=lease_duration_seconds
            )
        )

        statement = (
            update(Operation)
            .where(
                Operation.idempotency_key == idempotency_key,
                Operation.lease_token == token,
                Operation.status == "in_progress",
                Operation.lease_expires_at > func.now(),
            )
            .values(
                lease_expires_at=new_expiry,
                updated_at=func.now(),
            )
            .returning(Operation.id)
        )

        return session.scalar(statement) is not None

    @staticmethod
    def recover_expired_operations(session: Session) -> int:
        """
        Move expired in-progress operations into recovery_required.
        """

        statement = (
            update(Operation)
            .where(
                Operation.status == "in_progress",
                Operation.lease_expires_at <= func.now(),
            )
            .values(
                status="recovery_required",
                lease_token=None,
                lease_expires_at=None,
                updated_at=func.now(),
            )
            .returning(Operation.id)
        )

        return len(session.scalars(statement).all())

    @staticmethod
    def get_recovery_required_operations(
        session: Session,
    ) -> list[dict[str, Any]]:
        statement = (
            select(
                Operation.id,
                Operation.idempotency_key,
                Operation.tool_name,
                Operation.arguments_hash,
                Operation.status,
                Operation.result,
                Operation.created_at,
                Operation.updated_at,
                Operation.attempt_count,
            )
            .where(Operation.status == "recovery_required")
            .order_by(Operation.updated_at.asc())
        )

        return [
            dict(row)
            for row in session.execute(statement).mappings().all()
        ]

    @staticmethod
    def _insert_reconciliation(
        session: Session,
        operation: Operation,
        decision: str,
        evidence: str,
        reconciled_by: str,
        previous_result: Any,
        reconciled_result: Any,
    ) -> None:
        reconciliation = OperationReconciliation(
            operation_id=operation.id,
            decision=decision,
            evidence=evidence,
            reconciled_by=reconciled_by,
            previous_result=previous_result,
            reconciled_result=reconciled_result,
        )

        session.add(reconciliation)
        session.flush()

    @staticmethod
    def reconcile_operation(
        session: Session,
        idempotency_key: str,
        decision: str,
        evidence: str,
        reconciled_by: str,
        reconciled_result: Any = None,
    ) -> bool:
        """
        Reconcile an operation and record its history.

        The caller must wrap this method in one transaction.
        The row lock prevents two concurrent reconciliations
        from processing the same recovery operation.
        """

        statement = (
            select(Operation)
            .where(
                Operation.idempotency_key == idempotency_key,
                Operation.status == "recovery_required",
            )
            .with_for_update()
        )

        operation = session.scalar(statement)

        if operation is None:
            return False

        previous_result = operation.result

        if decision == "completed":
            final_result = reconciled_result
        else:
            final_result = (
                "Operation reconciled as failed based on external evidence."
            )

        operation.status = decision
        operation.result = final_result
        operation.lease_token = None
        operation.lease_expires_at = None
        operation.updated_at = func.now()

        session.flush()

        IdempotencyRepository._insert_reconciliation(
            session=session,
            operation=operation,
            decision=decision,
            evidence=evidence,
            reconciled_by=reconciled_by,
            previous_result=previous_result,
            reconciled_result=(
                reconciled_result if decision == "completed" else None
            ),
        )

        return True

    @staticmethod
    def get_reconciliation_history(
        session: Session,
        idempotency_key: str,
    ) -> list[dict[str, Any]]:
        statement = (
            select(
                OperationReconciliation.id.label("reconciliation_id"),
                Operation.idempotency_key,
                OperationReconciliation.decision,
                OperationReconciliation.evidence,
                OperationReconciliation.reconciled_at,
                OperationReconciliation.reconciled_by,
                OperationReconciliation.previous_result,
                OperationReconciliation.reconciled_result,
            )
            .join(
                Operation,
                Operation.id == OperationReconciliation.operation_id,
            )
            .where(Operation.idempotency_key == idempotency_key)
            .order_by(
                OperationReconciliation.reconciled_at.asc(),
                OperationReconciliation.id.asc(),
            )
        )

        return [
            dict(row)
            for row in session.execute(statement).mappings().all()
        ]

    @staticmethod
    def cancel(
        session: Session,
        idempotency_key: str,
        lease_token: str | UUID,
        result: Any = "Tool execution cancelled by user.",
    ) -> bool:
        token = UUID(str(lease_token))

        statement = (
            update(Operation)
            .where(
                Operation.idempotency_key == idempotency_key,
                Operation.lease_token == token,
                Operation.status == "in_progress",
                Operation.lease_expires_at > func.now(),
            )
            .values(
                status="cancelled",
                result=result,
                lease_token=None,
                lease_expires_at=None,
                updated_at=func.now(),
            )
            .returning(Operation.id)
        )

        return session.scalar(statement) is not None
