from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, text, update

from database.connection import SessionLocal
from database.models import Operation, OperationReconciliation
from repositories.idempotency_repository import IdempotencyRepository
from services.idempotency_service import IdempotencyService

from datetime import datetime, timedelta, timezone
from sqlalchemy.exc import IntegrityError


service = IdempotencyService()


def unique_key(prefix="pytest"):
    return f"{prefix}-{uuid4().hex}"


def create_claimed_operation(prefix="pytest"):
    key = unique_key(prefix)

    result = service.claim(
        idempotency_key=key,
        tool_name="calculator",
        arguments={"expression": "10 + 5"},
        lease_duration_seconds=60,
    )

    assert result["status"] == "new"
    assert result["lease_token"] is not None

    return key, result["lease_token"]


def expire_operation(key):
    with SessionLocal() as session:
        with session.begin():
            session.execute(
                update(Operation)
                .where(Operation.idempotency_key == key)
                .values(
                    lease_expires_at=text(
                        "now() - interval '1 second'"
                    )
                )
            )


def cleanup_operation(key):
    """
    Delete test reconciliation history first because the FK
    intentionally uses ON DELETE RESTRICT.
    """
    with SessionLocal() as session:
        with session.begin():
            operation_id = session.scalar(
                select(Operation.id).where(
                    Operation.idempotency_key == key
                )
            )

            if operation_id is not None:
                session.execute(
                    delete(OperationReconciliation).where(
                        OperationReconciliation.operation_id
                        == operation_id
                    )
                )

                session.execute(
                    delete(Operation).where(
                        Operation.id == operation_id
                    )
                )


def move_to_recovery(key):
    expire_operation(key)

    recovered_count = service.recover_expired_operations()

    assert recovered_count >= 1


# ---------------------------------------------------------
# Claim and lookup
# ---------------------------------------------------------


def test_concurrent_claims_create_only_one_operation():
    worker_count = 8
    key = unique_key("pytest-concurrent")
    barrier = Barrier(worker_count)

    def claim_operation():
        barrier.wait()

        return service.claim(
            idempotency_key=key,
            tool_name="calculator",
            arguments={"expression": "10 + 5"},
            lease_duration_seconds=60,
        )

    try:
        with ThreadPoolExecutor(
            max_workers=worker_count
        ) as executor:
            results = list(
                executor.map(
                    lambda _: claim_operation(),
                    range(worker_count),
                )
            )

        statuses = [item["status"] for item in results]

        assert statuses.count("new") == 1
        assert statuses.count("in_progress") == worker_count - 1

        lease_tokens = [
            item["lease_token"]
            for item in results
            if item["lease_token"] is not None
        ]

        assert len(lease_tokens) == 1

        with SessionLocal() as session:
            operation = IdempotencyRepository.get_by_idempotency_key(
                session,
                key,
            )

            assert operation is not None
            assert operation.status == "in_progress"
            assert operation.attempt_count == 1

    finally:
        cleanup_operation(key)


def test_lookup_returns_none_for_unknown_key():
    assert service.lookup(unique_key()) is None


def test_lookup_returns_existing_operation():
    key, _ = create_claimed_operation()

    try:
        result = service.lookup(
            key,
            "calculator",
            {"expression": "10 + 5"},
        )

        assert result == {
            "status": "in_progress",
            "result": None,
        }

    finally:
        cleanup_operation(key)


def test_lookup_detects_argument_conflict():
    key, _ = create_claimed_operation()

    try:
        result = service.lookup(
            key,
            "calculator",
            {"expression": "100 + 200"},
        )

        assert result == {
            "status": "conflict",
            "result": None,
        }

    finally:
        cleanup_operation(key)


def test_claim_returns_existing_operation_without_new_lease():
    key, original_token = create_claimed_operation()

    try:
        result = service.claim(
            idempotency_key=key,
            tool_name="calculator",
            arguments={"expression": "10 + 5"},
            lease_duration_seconds=60,
        )

        assert result["status"] == "in_progress"
        assert result["result"] is None
        assert result["lease_token"] is None

    finally:
        cleanup_operation(key)


def test_claim_rejects_same_key_with_different_arguments():
    key, _ = create_claimed_operation()

    try:
        result = service.claim(
            idempotency_key=key,
            tool_name="calculator",
            arguments={"expression": "20 + 30"},
            lease_duration_seconds=60,
        )

        assert result["status"] == "conflict"
        assert result["lease_token"] is None

    finally:
        cleanup_operation(key)


def test_claim_rejects_nonpositive_lease_duration():
    with pytest.raises(ValueError):
        service.claim(
            idempotency_key=unique_key(),
            tool_name="calculator",
            arguments={"expression": "1 + 1"},
            lease_duration_seconds=0,
        )


# ---------------------------------------------------------
# Finish
# ---------------------------------------------------------


def test_finish_succeeds_with_valid_lease():
    key, token = create_claimed_operation()

    try:
        finished = service.finish(
            key,
            token,
            "15",
        )

        assert finished is True

        result = service.lookup(key)

        assert result == {
            "status": "completed",
            "result": "15",
        }

        with SessionLocal() as session:
            operation = IdempotencyRepository.get_by_idempotency_key(
                session,
                key,
            )

            assert operation.lease_token is None
            assert operation.lease_expires_at is None

    finally:
        cleanup_operation(key)


def test_finish_can_mark_operation_failed():
    key, token = create_claimed_operation()

    try:
        finished = service.finish(
            key,
            token,
            "Calculator execution failed.",
            status="failed",
        )

        assert finished is True

        result = service.lookup(key)

        assert result["status"] == "failed"
        assert result["result"] == "Calculator execution failed."

    finally:
        cleanup_operation(key)


def test_finish_rejects_invalid_lease_token():
    key, original_token = create_claimed_operation()

    try:
        finished = service.finish(
            key,
            uuid4(),
            "15",
        )

        assert finished is False

        result = service.lookup(key)

        assert result["status"] == "in_progress"
        assert result["result"] is None

    finally:
        cleanup_operation(key)


def test_finish_rejects_expired_lease():
    key, token = create_claimed_operation()

    try:
        expire_operation(key)

        finished = service.finish(
            key,
            token,
            "15",
        )

        assert finished is False

        result = service.lookup(key)

        assert result["status"] == "in_progress"
        assert result["result"] is None

    finally:
        cleanup_operation(key)


def test_finish_rejects_invalid_status():
    key, token = create_claimed_operation()

    try:
        with pytest.raises(ValueError):
            service.finish(
                key,
                token,
                "15",
                status="cancelled",
            )

    finally:
        cleanup_operation(key)


# ---------------------------------------------------------
# Lease renewal
# ---------------------------------------------------------


def test_renew_lease_succeeds_for_valid_owner():
    key, token = create_claimed_operation()

    try:
        with SessionLocal() as session:
            old_expiry = session.scalar(
                select(Operation.lease_expires_at).where(
                    Operation.idempotency_key == key
                )
            )

        renewed = service.renew_lease(
            key,
            token,
            lease_duration_seconds=180,
        )

        assert renewed is True

        with SessionLocal() as session:
            new_expiry = session.scalar(
                select(Operation.lease_expires_at).where(
                    Operation.idempotency_key == key
                )
            )

        assert new_expiry > old_expiry

    finally:
        cleanup_operation(key)


def test_renew_lease_rejects_invalid_token():
    key, _ = create_claimed_operation()

    try:
        renewed = service.renew_lease(
            key,
            uuid4(),
            lease_duration_seconds=120,
        )

        assert renewed is False

    finally:
        cleanup_operation(key)


def test_renew_lease_rejects_expired_lease():
    key, token = create_claimed_operation()

    try:
        expire_operation(key)

        renewed = service.renew_lease(
            key,
            token,
            lease_duration_seconds=120,
        )

        assert renewed is False

    finally:
        cleanup_operation(key)


def test_renew_lease_rejects_nonpositive_duration():
    key, token = create_claimed_operation()

    try:
        with pytest.raises(ValueError):
            service.renew_lease(
                key,
                token,
                lease_duration_seconds=0,
            )

    finally:
        cleanup_operation(key)


# ---------------------------------------------------------
# Recovery
# ---------------------------------------------------------


def test_expired_operation_can_be_recovered():
    key, _ = create_claimed_operation()

    try:
        expire_operation(key)

        recovered_count = service.recover_expired_operations()

        assert recovered_count >= 1

        result = service.lookup(key)

        assert result["status"] == "recovery_required"

    finally:
        cleanup_operation(key)


def test_recovery_queue_contains_expired_operation():
    key, _ = create_claimed_operation()

    try:
        move_to_recovery(key)

        recovery_items = service.get_recovery_required_operations()

        matching_items = [
            item
            for item in recovery_items
            if item["idempotency_key"] == key
        ]

        assert len(matching_items) == 1
        assert matching_items[0]["status"] == "recovery_required"
        assert matching_items[0]["tool_name"] == "calculator"

    finally:
        cleanup_operation(key)


def test_recovered_operation_cannot_be_finished_by_old_worker():
    key, token = create_claimed_operation()

    try:
        move_to_recovery(key)

        finished = service.finish(
            key,
            token,
            "15",
        )

        assert finished is False

        result = service.lookup(key)

        assert result["status"] == "recovery_required"

    finally:
        cleanup_operation(key)


# ---------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------


def test_reconcile_operation_as_completed():
    key, _ = create_claimed_operation()

    try:
        move_to_recovery(key)

        reconciled = service.reconcile_operation(
            idempotency_key=key,
            decision="completed",
            evidence="External system confirms successful execution.",
            reconciled_by="pytest",
            reconciled_result="15",
        )

        assert reconciled is True

        result = service.lookup(key)

        assert result["status"] == "completed"
        assert result["result"] == "15"

        history = service.get_reconciliation_history(key)

        assert len(history) == 1
        assert history[0]["decision"] == "completed"
        assert history[0]["evidence"] == (
            "External system confirms successful execution."
        )
        assert history[0]["reconciled_by"] == "pytest"
        assert history[0]["reconciled_result"] == "15"

    finally:
        cleanup_operation(key)


def test_reconcile_operation_as_failed():
    key, _ = create_claimed_operation()

    try:
        move_to_recovery(key)

        reconciled = service.reconcile_operation(
            idempotency_key=key,
            decision="failed",
            evidence="External system confirms execution did not complete.",
            reconciled_by="pytest",
        )

        assert reconciled is True

        result = service.lookup(key)

        assert result["status"] == "failed"
        assert result["result"] == (
            "Operation reconciled as failed based on external evidence."
        )

        history = service.get_reconciliation_history(key)

        assert len(history) == 1
        assert history[0]["decision"] == "failed"
        assert history[0]["reconciled_result"] is None

    finally:
        cleanup_operation(key)


def test_reconciliation_requires_recovery_status():
    key, _ = create_claimed_operation()

    try:
        reconciled = service.reconcile_operation(
            idempotency_key=key,
            decision="completed",
            evidence="External verification.",
            reconciled_by="pytest",
            reconciled_result="15",
        )

        assert reconciled is False

    finally:
        cleanup_operation(key)


def test_reconciliation_rejects_invalid_decision():
    with pytest.raises(ValueError):
        service.reconcile_operation(
            idempotency_key=unique_key(),
            decision="unknown",
            evidence="Evidence",
            reconciled_by="pytest",
        )


def test_completed_reconciliation_requires_result():
    with pytest.raises(ValueError):
        service.reconcile_operation(
            idempotency_key=unique_key(),
            decision="completed",
            evidence="Evidence",
            reconciled_by="pytest",
            reconciled_result="",
        )


def test_reconciliation_requires_nonempty_evidence():
    with pytest.raises(ValueError):
        service.reconcile_operation(
            idempotency_key=unique_key(),
            decision="failed",
            evidence=" ",
            reconciled_by="pytest",
        )


def test_reconciliation_history_is_rolled_back_on_insert_failure(
    monkeypatch,
):
    key, _ = create_claimed_operation()

    try:
        move_to_recovery(key)

        def fail_insert(*args, **kwargs):
            raise RuntimeError("Simulated history insertion failure.")

        monkeypatch.setattr(
            IdempotencyRepository,
            "_insert_reconciliation",
            staticmethod(fail_insert),
        )

        with pytest.raises(RuntimeError):
            service.reconcile_operation(
                idempotency_key=key,
                decision="completed",
                evidence="External verification.",
                reconciled_by="pytest",
                reconciled_result="15",
            )

        # The operation update must have rolled back.
        result = service.lookup(key)

        assert result["status"] == "recovery_required"

        # No reconciliation history should have been committed.
        assert service.get_reconciliation_history(key) == []

    finally:
        cleanup_operation(key)


# ---------------------------------------------------------
# Cancellation
# ---------------------------------------------------------


def test_cancel_succeeds_with_valid_lease():
    key, token = create_claimed_operation()

    try:
        cancelled = service.cancel(key, token)

        assert cancelled is True

        result = service.lookup(key)

        assert result["status"] == "cancelled"
        assert result["result"] == "Tool execution cancelled by user."

    finally:
        cleanup_operation(key)


def test_cancel_rejects_invalid_lease_token():
    key, _ = create_claimed_operation()

    try:
        cancelled = service.cancel(key, uuid4())

        assert cancelled is False

        result = service.lookup(key)

        assert result["status"] == "in_progress"

    finally:
        cleanup_operation(key)


def test_cancel_rejects_expired_lease():
    key, token = create_claimed_operation()

    try:
        expire_operation(key)

        cancelled = service.cancel(key, token)

        assert cancelled is False

    finally:
        cleanup_operation(key)


# ---------------------------------------------------------
# Additional lease and recovery coverage
# ---------------------------------------------------------


def test_new_operation_has_future_lease_expiration():
    key, _ = create_claimed_operation()

    try:
        with SessionLocal() as session:
            expiry = session.scalar(
                select(Operation.lease_expires_at).where(
                    Operation.idempotency_key == key
                )
            )

            assert expiry is not None
            assert expiry > session.scalar(select(func.now()))

    finally:
        cleanup_operation(key)


def test_active_operation_is_not_recovered():
    key, _ = create_claimed_operation()

    try:
        service.recover_expired_operations()

        result = service.lookup(key)

        assert result["status"] == "in_progress"

    finally:
        cleanup_operation(key)


# ---------------------------------------------------------
# Additional recovery queue coverage
# ---------------------------------------------------------


def test_recovery_queue_excludes_operations_with_other_statuses():
    recovery_key, _ = create_claimed_operation()
    completed_key, completed_token = create_claimed_operation()

    try:
        move_to_recovery(recovery_key)

        assert service.finish(
            completed_key,
            completed_token,
            "Completed successfully.",
        )

        recovery_items = service.get_recovery_required_operations()

        recovery_keys = {
            item["idempotency_key"]
            for item in recovery_items
        }

        assert recovery_key in recovery_keys
        assert completed_key not in recovery_keys

    finally:
        cleanup_operation(recovery_key)
        cleanup_operation(completed_key)


def test_recovery_queue_is_ordered_by_updated_at():
    first_key, _ = create_claimed_operation()
    second_key, _ = create_claimed_operation()

    try:
        expire_operation(first_key)
        expire_operation(second_key)

        service.recover_expired_operations()

        first_timestamp = datetime.now(timezone.utc) - timedelta(minutes=2)
        second_timestamp = datetime.now(timezone.utc) - timedelta(minutes=1)

        with SessionLocal() as session:
            with session.begin():
                session.execute(
                    update(Operation)
                    .where(Operation.idempotency_key == first_key)
                    .values(updated_at=first_timestamp)
                )

                session.execute(
                    update(Operation)
                    .where(Operation.idempotency_key == second_key)
                    .values(updated_at=second_timestamp)
                )

        recovery_items = service.get_recovery_required_operations()

        matching_keys = [
            item["idempotency_key"]
            for item in recovery_items
            if item["idempotency_key"] in {first_key, second_key}
        ]

        assert matching_keys == [first_key, second_key]

    finally:
        cleanup_operation(first_key)
        cleanup_operation(second_key)


# ---------------------------------------------------------
# Additional reconciliation coverage
# ---------------------------------------------------------


def test_reconciliation_preserves_previous_result():
    key, _ = create_claimed_operation()

    try:
        with SessionLocal() as session:
            with session.begin():
                session.execute(
                    update(Operation)
                    .where(Operation.idempotency_key == key)
                    .values(result="Previously recorded result.")
                )

        move_to_recovery(key)

        reconciled = service.reconcile_operation(
            idempotency_key=key,
            decision="completed",
            evidence="External verification confirms success.",
            reconciled_by="pytest",
            reconciled_result="Verified final result.",
        )

        assert reconciled is True

        history = service.get_reconciliation_history(key)

        assert len(history) == 1
        assert history[0]["previous_result"] == (
            "Previously recorded result."
        )
        assert history[0]["reconciled_result"] == (
            "Verified final result."
        )

    finally:
        cleanup_operation(key)


def test_reconciliation_history_returns_chronological_order():
    key, _ = create_claimed_operation()

    try:
        move_to_recovery(key)

        with SessionLocal() as session:
            operation = IdempotencyRepository.get_by_idempotency_key(
                session,
                key,
            )
            operation_id = operation.id

        earlier = datetime.now(timezone.utc) - timedelta(minutes=2)
        later = datetime.now(timezone.utc) - timedelta(minutes=1)

        with SessionLocal() as session:
            with session.begin():
                session.add_all([
                    OperationReconciliation(
                        operation_id=operation_id,
                        decision="completed",
                        evidence="Earlier evidence.",
                        reconciled_by="pytest",
                        reconciled_at=earlier,
                        previous_result=None,
                        reconciled_result="Earlier result.",
                    ),
                    OperationReconciliation(
                        operation_id=operation_id,
                        decision="failed",
                        evidence="Later evidence.",
                        reconciled_by="pytest",
                        reconciled_at=later,
                        previous_result="Earlier result.",
                        reconciled_result=None,
                    ),
                ])

        history = service.get_reconciliation_history(key)

        assert len(history) == 2
        assert history[0]["evidence"] == "Earlier evidence."
        assert history[1]["evidence"] == "Later evidence."

    finally:
        cleanup_operation(key)


def test_reconciliation_history_returns_empty_for_unknown_key():
    assert service.get_reconciliation_history(unique_key()) == []


def test_reconciliation_rejects_empty_reconciled_by():
    key, _ = create_claimed_operation()

    try:
        move_to_recovery(key)

        with pytest.raises(ValueError):
            service.reconcile_operation(
                idempotency_key=key,
                decision="failed",
                evidence="External verification.",
                reconciled_by=" ",
            )

        assert service.lookup(key)["status"] == "recovery_required"

    finally:
        cleanup_operation(key)


def test_reconciliation_foreign_key_is_enforced():
    with pytest.raises(IntegrityError):
        with SessionLocal() as session:
            with session.begin():
                session.add(
                    OperationReconciliation(
                        operation_id=uuid4(),
                        decision="completed",
                        evidence="Test evidence.",
                        reconciled_by="pytest",
                        reconciled_result="15",
                    )
                )
                session.flush()
