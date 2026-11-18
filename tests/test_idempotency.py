import sqlite3
import pytest
from tools.idempotency import IdempotencyStore
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

def test_new_operation_can_be_claimed(tmp_path):
    store = IdempotencyStore(
        tmp_path / "test.db"
    )

    result = store.claim(
        "call_001",
        "send_message",
        {
            "recipient": "test@example.com",
            "message": "Hello"
        }
    )

    assert result["status"] == "new"


def test_duplicate_operation_is_detected(tmp_path):
    store = IdempotencyStore(
        tmp_path / "test.db"
    )

    arguments = {
        "recipient": "test@example.com",
        "message": "Hello"
    }

    claim = store.claim(
        "call_002",
        "send_message",
        arguments
    )

    store.finish(
        idempotency_key="call_002",
        lease_token=claim["lease_token"],
        result="Message approved (simulation only)."
    )

    result = store.claim(
        "call_002",
        "send_message",
        arguments
    )

    assert result["status"] == "completed"
    assert result["result"] == "Message approved (simulation only)."


def test_same_key_with_different_arguments_is_rejected(tmp_path):
    store = IdempotencyStore(
        tmp_path / "test.db"
    )

    store.claim(
        "call_003",
        "send_message",
        {
            "recipient": "first@example.com",
            "message": "Hello"
        }
    )

    result = store.claim(
        "call_003",
        "send_message",
        {
            "recipient": "second@example.com",
            "message": "Hello"
        }
    )

    assert result["status"] == "conflict"


def test_in_progress_operation_is_detected(tmp_path):
    store = IdempotencyStore(
        tmp_path / "test.db"
    )

    arguments = {"expression": "2 + 2"}

    store.claim(
        "call_004",
        "calculator",
        arguments
    )

    result = store.claim(
        "call_004",
        "calculator",
        arguments
    )

    assert result["status"] == "in_progress"


def test_failed_operation_is_not_reexecuted_automatically(tmp_path):
    store = IdempotencyStore(
        tmp_path / "test.db"
    )

    arguments = {"expression": "2 / 0"}

    claim = store.claim(
        "call_005",
        "calculator",
        arguments
    )

    store.finish(
        idempotency_key="call_005",
        lease_token=claim["lease_token"],
        result="Tool execution error: Division by zero.",
        status="failed"
    )

    result = store.claim(
        "call_005",
        "calculator",
        arguments
    )

    assert result["status"] == "failed"
    assert "Division by zero" in result["result"]


def test_lookup_returns_none_for_new_operation(tmp_path):
    store = IdempotencyStore(
        tmp_path / "test.db"
    )
    result = store.lookup("new-operation")

    assert result is None


def test_lookup_returns_completed_operation(tmp_path):
    store = IdempotencyStore(
        tmp_path / "test.db"
    )
    claim = store.claim(
        "operation-123",
        "send_message",
        {
            "recipient": "test@example.com",
            "message": "Hello"
        }
    )

    store.finish(
        idempotency_key="operation-123",
        lease_token=claim["lease_token"],
        result="Message approved (simulation only).",
        status="completed"
    )

    result = store.lookup("operation-123")

    assert result == {
        "status": "completed",
        "result": "Message approved (simulation only)."
    }

def test_concurrent_claim_allows_only_one_new_operation(tmp_path):
    store = IdempotencyStore(
        tmp_path / "concurrent_test.db"
    )

    def claim_operation():
        return store.claim(
            idempotency_key="concurrent_operation_001",
            tool_name="send_message",
            arguments={
                "recipient": "test@example.com",
                "message": "Hello"
            }
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(
            executor.map(
                lambda _: claim_operation(),
                range(8)
            )
        )

    statuses = [result["status"] for result in results]

    assert statuses.count("new") == 1
    assert statuses.count("in_progress") == 7

def test_new_operation_receives_lease(tmp_path):

    store = IdempotencyStore(
        tmp_path / "lease_test.db"
    )

    result = store.claim(
        idempotency_key="lease_test_001",
        tool_name="calculator",
        arguments={"expression": "10 + 5"}
    )

    assert result["status"] == "new"
    assert result["lease_token"] is not None

    with store._connect() as connection:

        operation = connection.execute(
            """
            SELECT *
            FROM operations
            WHERE idempotency_key = ?
            """,
            ("lease_test_001",)
        ).fetchone()

    assert operation["lease_token"] == result["lease_token"]
    assert operation["attempt_count"] == 1
    assert operation["lease_expires_at"] is not None

def test_operation_can_be_finished_with_valid_lease(tmp_path):

    store = IdempotencyStore(
        tmp_path / "finish_test.db"
    )

    claim = store.claim(
        idempotency_key="finish_001",
        tool_name="calculator",
        arguments={"expression": "10 + 5"}
    )

    result = store.finish(
        idempotency_key="finish_001",
        lease_token=claim["lease_token"],
        result="15"
    )

    assert result is True

    operation = store.lookup("finish_001")

    assert operation["status"] == "completed"
    assert operation["result"] == "15"

def test_operation_cannot_be_finished_with_invalid_lease(tmp_path):

    store = IdempotencyStore(
        tmp_path / "invalid_lease_test.db"
    )

    store.claim(
        idempotency_key="finish_002",
        tool_name="calculator",
        arguments={"expression": "10 + 5"}
    )

    result = store.finish(
        idempotency_key="finish_002",
        lease_token="incorrect-token",
        result="15"
    )

    assert result is False

    operation = store.lookup("finish_002")

    assert operation["status"] == "in_progress"
    assert operation["result"] is None

def test_operation_has_future_lease_expiration(tmp_path):

    store = IdempotencyStore(
        tmp_path / "future_lease.db"
    )

    result = store.claim(
        idempotency_key="future_lease_001",
        tool_name="calculator",
        arguments={"expression": "10 + 5"},
        lease_duration_seconds=60
    )

    with store._connect() as connection:
        operation = connection.execute(
            """
            SELECT lease_expires_at
            FROM operations
            WHERE idempotency_key = ?
            """,
            ("future_lease_001",)
        ).fetchone()

    expiration = datetime.fromisoformat(
        operation["lease_expires_at"]
    )

    assert expiration > datetime.now(timezone.utc)

def test_expired_operation_requires_recovery(tmp_path):

    store = IdempotencyStore(
        tmp_path / "expired_test.db"
    )

    claim = store.claim(
        idempotency_key="expired_001",
        tool_name="calculator",
        arguments={"expression": "10 + 5"}
    )

    with store._connect() as connection:
        connection.execute(
            """
            UPDATE operations
            SET lease_expires_at = ?
            WHERE idempotency_key = ?
            """,
            (
                "2000-01-01T00:00:00+00:00",
                "expired_001"
            )
        )

    recovered_count = store.recover_expired_operations()

    assert recovered_count == 1

    operation = store.lookup("expired_001")

    assert operation["status"] == "recovery_required"
    assert operation["result"] is None

def test_active_operation_is_not_recovered(tmp_path):

    store = IdempotencyStore(
        tmp_path / "active_test.db"
    )

    store.claim(
        idempotency_key="active_001",
        tool_name="calculator",
        arguments={"expression": "10 + 5"},
        lease_duration_seconds=300
    )

    recovered_count = store.recover_expired_operations()

    assert recovered_count == 0

    operation = store.lookup("active_001")

    assert operation["status"] == "in_progress"

def test_old_worker_cannot_finish_after_recovery(tmp_path):

    store = IdempotencyStore(
        tmp_path / "stale_worker_test.db"
    )

    claim = store.claim(
        idempotency_key="stale_001",
        tool_name="calculator",
        arguments={"expression": "10 + 5"}
    )

    with store._connect() as connection:
        connection.execute(
            """
            UPDATE operations
            SET lease_expires_at = ?
            WHERE idempotency_key = ?
            """,
            (
                "2000-01-01T00:00:00+00:00",
                "stale_001"
            )
        )

    store.recover_expired_operations()

    result = store.finish(
        idempotency_key="stale_001",
        lease_token=claim["lease_token"],
        result="15"
    )

    assert result is False

    operation = store.lookup("stale_001")

    assert operation["status"] == "recovery_required"

def test_valid_owner_can_renew_lease(tmp_path):
    store = IdempotencyStore(tmp_path / "renew_valid.db")

    claim = store.claim(
        "renew_001",
        "calculator",
        {"expression": "5 + 5"},
        lease_duration_seconds=1
    )

    renewed = store.renew_lease(
        idempotency_key="renew_001",
        lease_token=claim["lease_token"],
        lease_duration_seconds=300
    )

    assert renewed is True

    with store._connect() as connection:
        operation = connection.execute(
            """
            SELECT lease_expires_at
            FROM operations
            WHERE idempotency_key = ?
            """,
            ("renew_001",)
        ).fetchone()

    expiry = datetime.fromisoformat(operation["lease_expires_at"])
    assert expiry > datetime.now(timezone.utc)

def test_invalid_owner_cannot_renew_lease(tmp_path):
    store = IdempotencyStore(tmp_path / "renew_invalid.db")

    store.claim(
        "renew_002",
        "calculator",
        {"expression": "5 + 5"}
    )

    renewed = store.renew_lease(
        idempotency_key="renew_002",
        lease_token="incorrect-token",
        lease_duration_seconds=300
    )

    assert renewed is False

def test_expired_lease_cannot_be_renewed(tmp_path):
    store = IdempotencyStore(tmp_path / "renew_expired.db")

    claim = store.claim(
        "renew_003",
        "calculator",
        {"expression": "5 + 5"}
    )

    with store._connect() as connection:
        connection.execute(
            """
            UPDATE operations
            SET lease_expires_at = ?
            WHERE idempotency_key = ?
            """,
            ("2000-01-01T00:00:00+00:00", "renew_003")
        )

    renewed = store.renew_lease(
        idempotency_key="renew_003",
        lease_token=claim["lease_token"],
        lease_duration_seconds=300
    )

    assert renewed is False

def test_completed_operation_cannot_renew_lease(tmp_path):
    store = IdempotencyStore(tmp_path / "renew_completed.db")

    claim = store.claim(
        "renew_004",
        "calculator",
        {"expression": "5 + 5"}
    )

    finished = store.finish(
        idempotency_key="renew_004",
        lease_token=claim["lease_token"],
        result="10"
    )

    assert finished is True

    renewed = store.renew_lease(
        idempotency_key="renew_004",
        lease_token=claim["lease_token"],
        lease_duration_seconds=300
    )

    assert renewed is False

def test_recovery_required_operations_can_be_listed(tmp_path):
    store = IdempotencyStore(tmp_path / "recovery_list.db")

    claim = store.claim(
        "recovery_list_001",
        "calculator",
        {"expression": "5 + 5"}
    )

    with store._connect() as connection:
        connection.execute(
            """
            UPDATE operations
            SET lease_expires_at = ?
            WHERE idempotency_key = ?
            """,
            ("2000-01-01T00:00:00+00:00", "recovery_list_001")
        )

    store.recover_expired_operations()

    operations = store.get_recovery_required_operations()

    assert len(operations) == 1
    assert operations[0]["idempotency_key"] == "recovery_list_001"
    assert operations[0]["tool_name"] == "calculator"
    assert operations[0]["status"] == "recovery_required"
    assert operations[0]["attempt_count"] == 1

def test_recovery_list_excludes_other_statuses(tmp_path):
    store = IdempotencyStore(tmp_path / "recovery_filter.db")

    store.claim(
        "active_001",
        "calculator",
        {"expression": "5 + 5"}
    )

    completed_claim = store.claim(
        "completed_001",
        "calculator",
        {"expression": "10 + 5"}
    )

    store.finish(
        idempotency_key="completed_001",
        lease_token=completed_claim["lease_token"],
        result="15"
    )

    operations = store.get_recovery_required_operations()

    assert operations == []

def test_recovery_list_is_empty_when_no_operations_need_recovery(tmp_path):
    store = IdempotencyStore(tmp_path / "recovery_empty.db")

    operations = store.get_recovery_required_operations()

    assert operations == []

def test_valid_owner_can_cancel_operation(tmp_path):
    store = IdempotencyStore(tmp_path / "cancel_valid.db")

    claim = store.claim(
        "cancel_001",
        "send_message",
        {
            "recipient": "test@example.com",
            "message": "Hello"
        }
    )

    cancelled = store.cancel(
        idempotency_key="cancel_001",
        lease_token=claim["lease_token"]
    )

    assert cancelled is True

    operation = store.lookup("cancel_001")

    assert operation["status"] == "cancelled"
    assert operation["result"] == "Tool execution cancelled by user."

def test_invalid_owner_cannot_cancel_operation(tmp_path):
    store = IdempotencyStore(tmp_path / "cancel_invalid.db")

    store.claim(
        "cancel_002",
        "send_message",
        {"recipient": "test@example.com", "message": "Hello"}
    )

    cancelled = store.cancel(
        idempotency_key="cancel_002",
        lease_token="invalid-token"
    )

    assert cancelled is False

    operation = store.lookup("cancel_002")
    assert operation["status"] == "in_progress"

def test_expired_operation_cannot_be_cancelled_by_old_owner(tmp_path):
    store = IdempotencyStore(tmp_path / "cancel_expired.db")

    claim = store.claim(
        "cancel_003",
        "send_message",
        {"recipient": "test@example.com", "message": "Hello"}
    )

    with store._connect() as connection:
        connection.execute(
            """
            UPDATE operations
            SET lease_expires_at = ?
            WHERE idempotency_key = ?
            """,
            ("2000-01-01T00:00:00+00:00", "cancel_003")
        )

    store.recover_expired_operations()

    cancelled = store.cancel(
        idempotency_key="cancel_003",
        lease_token=claim["lease_token"]
    )

    assert cancelled is False

    operation = store.lookup("cancel_003")
    assert operation["status"] == "recovery_required"

def test_expired_lease_cannot_be_finished_before_recovery(tmp_path):
    store = IdempotencyStore(tmp_path / "expired_finish.db")

    claim = store.claim(
        idempotency_key="expired_finish_001",
        tool_name="calculator",
        arguments={"expression": "5 + 5"}
    )

    assert claim["status"] == "new"

    # Expire the lease without running the recovery process.
    with store._connect() as connection:
        connection.execute(
            """
            UPDATE operations
            SET lease_expires_at = ?
            WHERE idempotency_key = ?
            """,
            ("2000-01-01T00:00:00+00:00", "expired_finish_001")
        )

    finished = store.finish(
        idempotency_key="expired_finish_001",
        lease_token=claim["lease_token"],
        result="10"
    )

    assert finished is False

    # The operation must not be marked completed.
    operation = store.lookup("expired_finish_001")

    assert operation["status"] == "in_progress"
    assert operation["result"] is None

    # Recovery should subsequently identify the expired operation.
    recovered = store.recover_expired_operations()

    assert recovered == 1

    operation = store.lookup("expired_finish_001")

    assert operation["status"] == "recovery_required"
    assert operation["result"] is None


def test_reconciliation_table_is_created(tmp_path):
    store = IdempotencyStore(
        tmp_path / "test_idempotency.db"
    )

    with store._connect() as connection:
        result = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            AND name = 'operation_reconciliations'
            """
        ).fetchone()

    assert result is not None


def test_reconciliation_foreign_key_is_enforced(tmp_path):
    store = IdempotencyStore(
        tmp_path / "test_idempotency.db"
    )

    with store._connect() as connection:
        foreign_keys_enabled = connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0]

        assert foreign_keys_enabled == 1

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO operation_reconciliations (
                    idempotency_key,
                    decision,
                    evidence,
                    reconciled_at,
                    reconciled_by
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "nonexistent_operation",
                    "completed",
                    "Test evidence",
                    "2026-11-18T12:00:00+00:00",
                    "test_operator"
                )
            )


def create_recovery_required_operation(store, key="test-operation-001"):
    """Insert an operation that is eligible for reconciliation."""
    with store._connect() as connection:
        connection.execute(
            """
            INSERT INTO operations (
                idempotency_key,
                tool_name,
                arguments_hash,
                status,
                result,
                created_at,
                updated_at,
                lease_expires_at,
                lease_token,
                attempt_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key,
                "send_message",
                "test-arguments-hash",
                "recovery_required",
                "Original uncertain outcome",
                "2026-11-19T00:00:00+00:00",
                "2026-11-19T00:00:00+00:00",
                None,
                None,
                1,
            ),
        )
    return key


def get_operation(store, key):
    with store._connect() as connection:
        return connection.execute(
            """
            SELECT *
            FROM operations
            WHERE idempotency_key = ?
            """,
            (key,),
        ).fetchone()


def get_reconciliation_count(store, key):
    with store._connect() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM operation_reconciliations
            WHERE idempotency_key = ?
            """,
            (key,),
        ).fetchone()
    return row["count"]


@pytest.fixture
def reconciliation_store(tmp_path):
    return IdempotencyStore(tmp_path / "reconciliation_test.db")


def test_reconcile_completed_operation(reconciliation_store):
    key = create_recovery_required_operation(reconciliation_store)
    verified_result = "Message successfully delivered."

    result = reconciliation_store.reconcile_operation(
        idempotency_key=key,
        decision="completed",
        evidence="External service confirms the message was delivered.",
        reconciled_by="test_operator",
        reconciled_result=verified_result,
    )

    operation = get_operation(reconciliation_store, key)

    assert result is True
    assert operation["status"] == "completed"
    assert operation["result"] == verified_result
    assert operation["lease_token"] is None
    assert operation["lease_expires_at"] is None
    assert get_reconciliation_count(reconciliation_store, key) == 1

def test_reconcile_failed_operation(reconciliation_store):
    key = create_recovery_required_operation(reconciliation_store)

    result = reconciliation_store.reconcile_operation(
        idempotency_key=key,
        decision="failed",
        evidence="External service confirms the operation was not executed.",
        reconciled_by="test_operator",
    )

    operation = get_operation(reconciliation_store, key)

    assert result is True
    assert operation["status"] == "failed"
    assert "reconciled as failed" in operation["result"].lower()
    assert get_reconciliation_count(reconciliation_store, key) == 1


@pytest.mark.parametrize("decision", ["unknown", "in_progress", "cancelled", ""])
def test_reconcile_rejects_invalid_decision(
    reconciliation_store,
    decision,
):
    key = create_recovery_required_operation(reconciliation_store)

    with pytest.raises(ValueError):
        reconciliation_store.reconcile_operation(
            idempotency_key=key,
            decision=decision,
            evidence="Some external evidence.",
            reconciled_by="test_operator",
        )

    operation = get_operation(reconciliation_store, key)

    assert operation["status"] == "recovery_required"
    assert get_reconciliation_count(reconciliation_store, key) == 0


@pytest.mark.parametrize("evidence", ["", "   ", "\n\t"])
def test_reconcile_rejects_empty_evidence(
    reconciliation_store,
    evidence,
):
    key = create_recovery_required_operation(reconciliation_store)

    with pytest.raises(ValueError):
        reconciliation_store.reconcile_operation(
            idempotency_key=key,
            decision="completed",
            evidence=evidence,
            reconciled_by="test_operator",
            reconciled_result="Verified external result.",
        )

    assert get_operation(reconciliation_store, key)["status"] == "recovery_required"
    assert get_reconciliation_count(reconciliation_store, key) == 0


@pytest.mark.parametrize("reconciled_by", ["", "   ", "\n\t"])
def test_reconcile_rejects_empty_operator(
    reconciliation_store,
    reconciled_by,
):
    key = create_recovery_required_operation(reconciliation_store)

    with pytest.raises(ValueError):
        reconciliation_store.reconcile_operation(
            idempotency_key=key,
            decision="completed",
            evidence="External service confirms delivery.",
            reconciled_by=reconciled_by,
            reconciled_result="Verified external result.",
        )

    assert get_operation(reconciliation_store, key)["status"] == "recovery_required"
    assert get_reconciliation_count(reconciliation_store, key) == 0


def test_reconcile_rejects_nonexistent_operation(reconciliation_store):
    result = reconciliation_store.reconcile_operation(
        idempotency_key="does-not-exist",
        decision="completed",
        evidence="External service confirms delivery.",
        reconciled_by="test_operator",
        reconciled_result="Verified external result."
    )

    assert result is False
    assert get_reconciliation_count(reconciliation_store, "does-not-exist") == 0


@pytest.mark.parametrize("status", ["completed", "failed", "in_progress", "cancelled"])
def test_reconcile_rejects_operation_not_requiring_recovery(
    reconciliation_store,
    status,
):
    key = create_recovery_required_operation(reconciliation_store)

    with reconciliation_store._connect() as connection:
        connection.execute(
            """
            UPDATE operations
            SET status = ?
            WHERE idempotency_key = ?
            """,
            (status, key),
        )

    result = reconciliation_store.reconcile_operation(
        idempotency_key=key,
        decision="completed",
        evidence="External service confirms delivery.",
        reconciled_by="test_operator",
        reconciled_result="Verified external result."
    )

    operation = get_operation(reconciliation_store, key)

    assert result is False
    assert operation["status"] == status
    assert get_reconciliation_count(reconciliation_store, key) == 0



def test_reconciliation_preserves_previous_result(reconciliation_store):
    key = create_recovery_required_operation(reconciliation_store)

    original_operation = get_operation(reconciliation_store, key)
    original_result = original_operation["result"]
    verified_result = "Message successfully delivered."

    result = reconciliation_store.reconcile_operation(
        idempotency_key=key,
        decision="completed",
        evidence="External service confirms successful execution.",
        reconciled_by="test_operator",
        reconciled_result=verified_result,
    )

    assert result is True

    operation = get_operation(reconciliation_store, key)

    with reconciliation_store._connect() as connection:
        history = connection.execute(
            """
            SELECT *
            FROM operation_reconciliations
            WHERE idempotency_key = ?
            """,
            (key,),
        ).fetchone()

    assert operation["status"] == "completed"
    assert operation["result"] == verified_result
    assert history["previous_result"] == original_result
    assert history["evidence"] == (
        "External service confirms successful execution."
    )
    assert history["decision"] == "completed"
    assert history["reconciled_by"] == "test_operator"


def test_reconciliation_history_failure_rolls_back_operation(
    reconciliation_store,
):
    key = create_recovery_required_operation(reconciliation_store)

    # Simulate a failure when reconciliation history is written.
    with reconciliation_store._connect() as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_reconciliation_insert
            BEFORE INSERT ON operation_reconciliations
            BEGIN
                SELECT RAISE(ABORT, 'Simulated history insertion failure');
            END;
            """
        )

    with pytest.raises(sqlite3.IntegrityError):
        reconciliation_store.reconcile_operation(
            idempotency_key=key,
            decision="completed",
            evidence="External service confirms successful execution.",
            reconciled_by="test_operator",
            reconciled_result="Verified external result."
        )

    operation = get_operation(reconciliation_store, key)

    assert operation["status"] == "recovery_required"
    assert operation["result"] == "Original uncertain outcome"
    assert get_reconciliation_count(reconciliation_store, key) == 0


def test_get_reconciliation_history_returns_empty_list(
    reconciliation_store,
):
    key = create_recovery_required_operation(reconciliation_store)

    history = reconciliation_store.get_reconciliation_history(key)

    assert history == []


def test_get_reconciliation_history_returns_empty_list_for_unknown_key(
    reconciliation_store,
):
    history = reconciliation_store.get_reconciliation_history(
        "unknown-operation"
    )

    assert history == []


def test_get_reconciliation_history_returns_record(
    reconciliation_store,
):
    key = create_recovery_required_operation(reconciliation_store)
    verified_result = "Message successfully delivered."
    evidence = "External service confirms successful execution."

    reconciliation_store.reconcile_operation(
        idempotency_key=key,
        decision="completed",
        evidence=evidence,
        reconciled_by="test_operator",
        reconciled_result=verified_result
    )

    history = reconciliation_store.get_reconciliation_history(key)

    assert len(history) == 1

    record = history[0]

    assert record["idempotency_key"] == key
    assert record["decision"] == "completed"
    assert record["reconciled_result"] == verified_result
    assert record["evidence"] == evidence
    assert record["reconciled_by"] == "test_operator"
    assert record["previous_result"] == "Original uncertain outcome"
    assert record["reconciliation_id"] is not None
    assert record["reconciled_at"] is not None


def test_get_reconciliation_history_returns_chronological_order(
    reconciliation_store,
):
    key = create_recovery_required_operation(reconciliation_store)

    with reconciliation_store._connect() as connection:
        connection.executemany(
            """
            INSERT INTO operation_reconciliations (
                idempotency_key,
                decision,
                evidence,
                reconciled_at,
                reconciled_by,
                previous_result
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    key,
                    "completed",
                    "Later evidence",
                    "2026-11-19T10:00:00+00:00",
                    "operator_2",
                    "Original result",
                ),
                (
                    key,
                    "failed",
                    "Earlier evidence",
                    "2026-11-19T09:00:00+00:00",
                    "operator_1",
                    "Original result",
                ),
            ],
        )

    history = reconciliation_store.get_reconciliation_history(key)

    assert len(history) == 2
    assert history[0]["evidence"] == "Earlier evidence"
    assert history[1]["evidence"] == "Later evidence"

def test_reconcile_completed_requires_verified_result(
    reconciliation_store,
):
    key = create_recovery_required_operation(reconciliation_store)

    with pytest.raises(ValueError, match="result"):
        reconciliation_store.reconcile_operation(
            idempotency_key=key,
            decision="completed",
            evidence="External service confirms successful execution.",
            reconciled_by="test_operator",
        )

    operation = get_operation(reconciliation_store, key)

    assert operation["status"] == "recovery_required"
    assert operation["result"] == "Original uncertain outcome"
    assert get_reconciliation_count(reconciliation_store, key) == 0

@pytest.mark.parametrize("reconciled_result", ["", "   ", "\n\t"])
def test_reconcile_completed_rejects_empty_verified_result(
    reconciliation_store,
    reconciled_result,
):
    key = create_recovery_required_operation(reconciliation_store)

    with pytest.raises(ValueError, match="result"):
        reconciliation_store.reconcile_operation(
            idempotency_key=key,
            decision="completed",
            evidence="External service confirms successful execution.",
            reconciled_by="test_operator",
            reconciled_result=reconciled_result,
        )

    operation = get_operation(reconciliation_store, key)

    assert operation["status"] == "recovery_required"
    assert get_reconciliation_count(reconciliation_store, key) == 0

def test_reconcile_completed_stores_verified_result(
    reconciliation_store,
):
    key = create_recovery_required_operation(reconciliation_store)
    verified_result = "Message successfully delivered to test@example.com."

    result = reconciliation_store.reconcile_operation(
        idempotency_key=key,
        decision="completed",
        evidence="External service confirms successful delivery.",
        reconciled_by="test_operator",
        reconciled_result=verified_result,
    )

    operation = get_operation(reconciliation_store, key)
    lookup = reconciliation_store.lookup(key)

    assert result is True
    assert operation["status"] == "completed"
    assert operation["result"] == verified_result

    assert lookup["status"] == "completed"
    assert lookup["result"] == verified_result

def test_reconcile_failed_does_not_require_verified_result(
    reconciliation_store,
):
    key = create_recovery_required_operation(reconciliation_store)

    result = reconciliation_store.reconcile_operation(
        idempotency_key=key,
        decision="failed",
        evidence="External service confirms the operation was not executed.",
        reconciled_by="test_operator",
    )

    operation = get_operation(reconciliation_store, key)

    assert result is True
    assert operation["status"] == "failed"
    assert "reconciled as failed" in operation["result"].lower()

def test_reconciliation_history_preserves_verified_result(
    reconciliation_store,
):
    key = create_recovery_required_operation(reconciliation_store)
    verified_result = "Payment transaction confirmed by external service."

    reconciliation_store.reconcile_operation(
        idempotency_key=key,
        decision="completed",
        evidence="External service confirms transaction.",
        reconciled_by="test_operator",
        reconciled_result=verified_result,
    )

    history = reconciliation_store.get_reconciliation_history(key)

    assert len(history) == 1
    assert history[0]["previous_result"] == "Original uncertain outcome"
    assert history[0]["reconciled_result"] == verified_result
