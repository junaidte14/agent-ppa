
import hashlib
import json
from typing import Any, Callable
from uuid import UUID

from sqlalchemy.orm import Session

from database.connection import SessionLocal
from repositories.idempotency_repository import IdempotencyRepository


class IdempotencyService:
    """
    Application service for idempotency, leases, recovery,
    cancellation, and reconciliation.

    This service owns SQLAlchemy sessions and transactions.
    """

    FAILED_RECONCILIATION_RESULT = (
        "Operation reconciled as failed based on external evidence."
    )

    def __init__(
        self,
        session_factory: Callable[[], Session] = SessionLocal,
    ):
        self.session_factory = session_factory

    @staticmethod
    def _hash_arguments(arguments: Any) -> str:
        canonical = json.dumps(
            arguments,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

        return hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _validate_positive_duration(
        lease_duration_seconds: int,
    ) -> None:
        if (
            isinstance(lease_duration_seconds, bool)
            or not isinstance(lease_duration_seconds, int)
            or lease_duration_seconds <= 0
        ):
            raise ValueError(
                "lease_duration_seconds must be a positive integer."
            )

    @staticmethod
    def _validate_nonempty_string(
        value: str,
        field_name: str,
    ) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string.")

    def lookup(
        self,
        idempotency_key: str,
        tool_name: str | None = None,
        arguments: Any = None,
    ) -> dict[str, Any] | None:
        self._validate_nonempty_string(
            idempotency_key,
            "idempotency_key",
        )

        arguments_hash = None

        if tool_name is not None and arguments is not None:
            arguments_hash = self._hash_arguments(arguments)

        with self.session_factory() as session:
            return IdempotencyRepository.lookup(
                session=session,
                idempotency_key=idempotency_key,
                tool_name=tool_name,
                arguments_hash=arguments_hash,
            )

    def claim(
        self,
        idempotency_key: str,
        tool_name: str,
        arguments: Any,
        lease_duration_seconds: int = 60,
    ) -> dict[str, Any]:
        self._validate_nonempty_string(
            idempotency_key,
            "idempotency_key",
        )
        self._validate_nonempty_string(tool_name, "tool_name")
        self._validate_positive_duration(lease_duration_seconds)

        arguments_hash = self._hash_arguments(arguments)

        with self.session_factory() as session:
            with session.begin():
                return IdempotencyRepository.claim(
                    session=session,
                    idempotency_key=idempotency_key,
                    tool_name=tool_name,
                    arguments_hash=arguments_hash,
                    lease_duration_seconds=lease_duration_seconds,
                )

    def finish(
        self,
        idempotency_key: str,
        lease_token: str | UUID,
        result: Any,
        status: str = "completed",
    ) -> bool:
        if status not in {"completed", "failed"}:
            raise ValueError(
                "status must be either 'completed' or 'failed'."
            )

        with self.session_factory() as session:
            with session.begin():
                return IdempotencyRepository.finish(
                    session=session,
                    idempotency_key=idempotency_key,
                    lease_token=lease_token,
                    result=result,
                    status=status,
                )

    def renew_lease(
        self,
        idempotency_key: str,
        lease_token: str | UUID,
        lease_duration_seconds: int = 60,
    ) -> bool:
        self._validate_positive_duration(lease_duration_seconds)

        with self.session_factory() as session:
            with session.begin():
                return IdempotencyRepository.renew_lease(
                    session=session,
                    idempotency_key=idempotency_key,
                    lease_token=lease_token,
                    lease_duration_seconds=lease_duration_seconds,
                )

    def recover_expired_operations(self) -> int:
        with self.session_factory() as session:
            with session.begin():
                return IdempotencyRepository.recover_expired_operations(
                    session
                )

    def get_recovery_required_operations(
        self,
    ) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            return IdempotencyRepository.get_recovery_required_operations(
                session
            )

    def reconcile_operation(
        self,
        idempotency_key: str,
        decision: str,
        evidence: str,
        reconciled_by: str,
        reconciled_result: Any = None,
    ) -> bool:
        if decision not in {"completed", "failed"}:
            raise ValueError(
                "decision must be either 'completed' or 'failed'."
            )

        self._validate_nonempty_string(evidence, "evidence")
        self._validate_nonempty_string(reconciled_by, "reconciled_by")

        if decision == "completed":
            if (
                not isinstance(reconciled_result, str)
                or not reconciled_result.strip()
            ):
                raise ValueError(
                    "A non-empty reconciled_result is required "
                    "when decision is 'completed'."
                )

        with self.session_factory() as session:
            with session.begin():
                return IdempotencyRepository.reconcile_operation(
                    session=session,
                    idempotency_key=idempotency_key,
                    decision=decision,
                    evidence=evidence,
                    reconciled_by=reconciled_by,
                    reconciled_result=reconciled_result,
                )

    def get_reconciliation_history(
        self,
        idempotency_key: str,
    ) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            return IdempotencyRepository.get_reconciliation_history(
                session=session,
                idempotency_key=idempotency_key,
            )

    def cancel(
        self,
        idempotency_key: str,
        lease_token: str | UUID,
        result: Any = "Tool execution cancelled by user.",
    ) -> bool:
        with self.session_factory() as session:
            with session.begin():
                return IdempotencyRepository.cancel(
                    session=session,
                    idempotency_key=idempotency_key,
                    lease_token=lease_token,
                    result=result,
                )


# Application-wide service instance.
idempotency_service = IdempotencyService()
