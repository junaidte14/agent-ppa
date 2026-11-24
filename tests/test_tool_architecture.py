
import json
from uuid import uuid4

import pytest

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import SQLAlchemyError

from database.connection import SessionLocal
from database.models import Operation, OperationReconciliation
from services.idempotency_service import IdempotencyService

from tools.policy import ToolPolicy

import tools.registry as registry


# ---------------------------------------------------------
# PostgreSQL test adapter
# ---------------------------------------------------------

class PostgreSQLTestIdempotencyStore:
    """
    Test adapter around the real PostgreSQL IdempotencyService.

    Each test receives a unique idempotency-key namespace.
    The adapter keeps test records isolated and provides
    a PostgreSQL-specific lease-expiration helper.
    """

    def __init__(self, service, prefix):
        self.service = service
        self.prefix = prefix

    def _key(self, idempotency_key):
        return f"{self.prefix}{idempotency_key}"

    def lookup(
        self,
        idempotency_key,
        tool_name=None,
        arguments=None,
    ):
        return self.service.lookup(
            self._key(idempotency_key),
            tool_name,
            arguments,
        )

    def claim(
        self,
        idempotency_key,
        tool_name,
        arguments,
        lease_duration_seconds=60,
    ):
        return self.service.claim(
            self._key(idempotency_key),
            tool_name,
            arguments,
            lease_duration_seconds,
        )

    def finish(
        self,
        idempotency_key,
        lease_token,
        result,
        status="completed",
    ):
        return self.service.finish(
            self._key(idempotency_key),
            lease_token,
            result,
            status,
        )

    def renew_lease(
        self,
        idempotency_key,
        lease_token,
        lease_duration_seconds=60,
    ):
        return self.service.renew_lease(
            self._key(idempotency_key),
            lease_token,
            lease_duration_seconds,
        )

    def cancel(
        self,
        idempotency_key,
        lease_token,
        result="Tool execution cancelled by user.",
    ):
        return self.service.cancel(
            self._key(idempotency_key),
            lease_token,
            result,
        )

    def reconcile_operation(
        self,
        idempotency_key,
        decision,
        evidence,
        reconciled_by,
        reconciled_result=None,
    ):
        return self.service.reconcile_operation(
            self._key(idempotency_key),
            decision,
            evidence,
            reconciled_by,
            reconciled_result,
        )

    def get_reconciliation_history(self, idempotency_key):
        return self.service.get_reconciliation_history(
            self._key(idempotency_key)
        )

    def expire_lease(self, idempotency_key):
        """
        Test helper: expire one in-progress operation using
        PostgreSQL timestamps.
        """

        with self.service.session_factory() as session:
            with session.begin():
                statement = (
                    update(Operation)
                    .where(
                        Operation.idempotency_key
                        == self._key(idempotency_key),
                        Operation.status == "in_progress",
                    )
                    .values(
                        lease_expires_at=(
                            func.now() - text("INTERVAL '1 second'")
                        ),
                        updated_at=func.now(),
                    )
                    .returning(Operation.id)
                )

                return session.scalar(statement) is not None

    def recover_expired_operations(self):
        """
        Test-scoped recovery.

        The production service recovers all expired operations.
        This adapter scopes recovery to the current test's keys
        so one test cannot modify another test's records.
        """

        with self.service.session_factory() as session:
            with session.begin():
                statement = (
                    update(Operation)
                    .where(
                        Operation.idempotency_key.like(
                            f"{self.prefix}%"
                        ),
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

    def cleanup(self):
        """Delete this test's reconciliation and operation rows."""

        with self.service.session_factory() as session:
            with session.begin():
                operation_ids = select(Operation.id).where(
                    Operation.idempotency_key.like(
                        f"{self.prefix}%"
                    )
                )

                session.execute(
                    delete(OperationReconciliation).where(
                        OperationReconciliation.operation_id.in_(
                            operation_ids
                        )
                    )
                )

                session.execute(
                    delete(Operation).where(
                        Operation.idempotency_key.like(
                            f"{self.prefix}%"
                        )
                    )
                )


# ---------------------------------------------------------
# Fixtures
# ---------------------------------------------------------

@pytest.fixture
def isolated_idempotency_store(monkeypatch):
    service = IdempotencyService(
        session_factory=SessionLocal
    )

    store = PostgreSQLTestIdempotencyStore(
        service=service,
        prefix=f"pytest-tool-arch-{uuid4().hex}:",
    )

    monkeypatch.setattr(
        registry,
        "idempotency_store",
        store,
    )

    yield store

    store.cleanup()


# ---------------------------------------------------------
# Tool registration and basic execution
# ---------------------------------------------------------

def test_all_tools_are_registered():
    assert "calculator" in registry.TOOL_REGISTRY
    assert "get_current_datetime" in registry.TOOL_REGISTRY
    assert "analyze_text" in registry.TOOL_REGISTRY


def test_tool_definitions_are_generated():
    names = [
        item["function"]["name"]
        for item in registry.TOOL_DEFINITIONS
    ]

    assert "calculator" in names
    assert "get_current_datetime" in names
    assert "analyze_text" in names


def test_calculator_execution():
    result = registry.execute_tool(
        "calculator",
        json.dumps({"expression": "10 + 5"}),
    )

    assert result == "15"


def test_invalid_calculator_arguments():
    result = registry.execute_tool(
        "calculator",
        json.dumps({"wrong_field": "10 + 5"}),
    )

    assert "Invalid arguments" in result


def test_unexpected_argument_is_rejected():
    result = registry.execute_tool(
        "calculator",
        json.dumps({
            "expression": "10 + 5",
            "admin": True,
        }),
    )

    assert "Invalid arguments" in result


def test_unknown_tool():
    result = registry.execute_tool(
        "unknown_tool",
        "{}",
    )

    assert "Unknown tool" in result


# ---------------------------------------------------------
# Authorization
# ---------------------------------------------------------

def test_authorized_tool_executes():
    policy = ToolPolicy(
        allowed_permissions=frozenset({"math:calculate"})
    )

    result = registry.execute_tool(
        "calculator",
        '{"expression": "10 + 5"}',
        policy=policy,
    )

    assert result == "15"


def test_unauthorized_tool_is_blocked():
    policy = ToolPolicy(
        allowed_permissions=frozenset()
    )

    result = registry.execute_tool(
        "calculator",
        '{"expression": "10 + 5"}',
        policy=policy,
    )

    assert "Tool authorization error" in result
    assert "math:calculate" in result


def test_authorization_precedes_argument_validation():
    policy = ToolPolicy(
        allowed_permissions=frozenset()
    )

    result = registry.execute_tool(
        "calculator",
        '{"unexpected": true}',
        policy=policy,
    )

    assert "Tool authorization error" in result
    assert "Invalid arguments" not in result


# ---------------------------------------------------------
# Approval behavior
# ---------------------------------------------------------

def test_approved_action_executes():
    policy = ToolPolicy(
        allowed_permissions=frozenset({"message:send"})
    )

    def approve_action(tool_name, arguments):
        assert tool_name == "send_message"
        assert arguments["recipient"] == "test@example.com"
        return True

    result = registry.execute_tool(
        "send_message",
        '{"recipient":"test@example.com","message":"Hello"}',
        policy=policy,
        approval_callback=approve_action,
    )

    assert "SIMULATION ONLY" in result


def test_rejected_action_does_not_execute():
    policy = ToolPolicy(
        allowed_permissions=frozenset({"message:send"})
    )

    def reject_action(tool_name, arguments):
        return False

    result = registry.execute_tool(
        "send_message",
        '{"recipient":"test@example.com","message":"Hello"}',
        policy=policy,
        approval_callback=reject_action,
    )

    assert "cancelled by user" in result


def test_approval_required_but_no_handler():
    policy = ToolPolicy(
        allowed_permissions=frozenset({"message:send"})
    )

    result = registry.execute_tool(
        "send_message",
        '{"recipient":"test@example.com","message":"Hello"}',
        policy=policy,
    )

    assert "No approval handler" in result
    assert "blocked" in result


def test_unauthorized_action_never_requests_approval():
    policy = ToolPolicy(
        allowed_permissions=frozenset()
    )

    approval_called = False

    def approve_action(tool_name, arguments):
        nonlocal approval_called
        approval_called = True
        return True

    result = registry.execute_tool(
        "send_message",
        '{"recipient":"test@example.com","message":"Hello"}',
        policy=policy,
        approval_callback=approve_action,
    )

    assert "Tool authorization error" in result
    assert approval_called is False


# ---------------------------------------------------------
# Idempotent execution
# ---------------------------------------------------------

def test_idempotent_operation_executes_only_once(
    isolated_idempotency_store,
    monkeypatch,
):
    tool = registry.TOOL_REGISTRY["calculator"]
    execution_count = 0

    def fake_calculator(expression):
        nonlocal execution_count
        execution_count += 1
        return f"result:{expression}"

    monkeypatch.setattr(tool, "function", fake_calculator)

    first_result = registry.execute_tool(
        "calculator",
        '{"expression": "10 + 5"}',
        idempotency_key="test-operation-001",
    )

    second_result = registry.execute_tool(
        "calculator",
        '{"expression": "10 + 5"}',
        idempotency_key="test-operation-001",
    )

    assert first_result == "result:10 + 5"
    assert second_result == first_result
    assert execution_count == 1


def test_idempotency_key_rejects_different_arguments(
    isolated_idempotency_store,
    monkeypatch,
):
    tool = registry.TOOL_REGISTRY["calculator"]
    execution_count = 0

    def fake_calculator(expression):
        nonlocal execution_count
        execution_count += 1
        return f"result:{expression}"

    monkeypatch.setattr(tool, "function", fake_calculator)

    registry.execute_tool(
        "calculator",
        '{"expression": "10 + 5"}',
        idempotency_key="test-operation-002",
    )

    result = registry.execute_tool(
        "calculator",
        '{"expression": "20 + 5"}',
        idempotency_key="test-operation-002",
    )

    assert "Idempotency conflict" in result
    assert execution_count == 1


def test_in_progress_operation_is_not_executed_again(
    isolated_idempotency_store,
    monkeypatch,
):
    tool = registry.TOOL_REGISTRY["calculator"]
    execution_count = 0

    def fake_calculator(expression):
        nonlocal execution_count
        execution_count += 1
        return f"result:{expression}"

    monkeypatch.setattr(tool, "function", fake_calculator)

    isolated_idempotency_store.claim(
        "test-operation-003",
        "calculator",
        {"expression": "10 + 5"},
    )

    result = registry.execute_tool(
        "calculator",
        '{"expression": "10 + 5"}',
        idempotency_key="test-operation-003",
    )

    assert "already in progress" in result
    assert execution_count == 0


def test_failed_operation_is_not_executed_again(
    isolated_idempotency_store,
    monkeypatch,
):
    tool = registry.TOOL_REGISTRY["calculator"]
    execution_count = 0

    def fake_calculator(expression):
        nonlocal execution_count
        execution_count += 1
        return f"result:{expression}"

    monkeypatch.setattr(tool, "function", fake_calculator)

    claim = isolated_idempotency_store.claim(
        "test-operation-004",
        "calculator",
        {"expression": "10 + 5"},
    )

    isolated_idempotency_store.finish(
        idempotency_key="test-operation-004",
        result="Previous simulated failure",
        lease_token=claim["lease_token"],
        status="failed",
    )

    result = registry.execute_tool(
        "calculator",
        '{"expression": "10 + 5"}',
        idempotency_key="test-operation-004",
    )

    assert "Automatic re-execution is blocked" in result
    assert execution_count == 0


# ---------------------------------------------------------
# Expired leases and recovery
# ---------------------------------------------------------

def test_recovery_required_operation_is_not_executed(
    isolated_idempotency_store,
    monkeypatch,
):
    execution_count = 0

    def fake_calculator(expression):
        nonlocal execution_count
        execution_count += 1
        return "10"

    monkeypatch.setattr(
        registry.TOOL_REGISTRY["calculator"],
        "function",
        fake_calculator,
    )

    isolated_idempotency_store.claim(
        "recovery_registry_001",
        "calculator",
        {"expression": "5 + 5"},
    )

    assert isolated_idempotency_store.expire_lease(
        "recovery_registry_001"
    )

    isolated_idempotency_store.recover_expired_operations()

    result = registry.execute_tool(
        tool_name="calculator",
        arguments='{"expression": "5 + 5"}',
        idempotency_key="recovery_registry_001",
    )

    assert "Recovery required" in result
    assert execution_count == 0


def test_lost_lease_during_execution_does_not_report_success(
    isolated_idempotency_store,
    monkeypatch,
):
    def fake_calculator(expression):
        assert isolated_idempotency_store.expire_lease(
            "lost_lease_001"
        )

        isolated_idempotency_store.recover_expired_operations()

        return "10"

    monkeypatch.setattr(
        registry.TOOL_REGISTRY["calculator"],
        "function",
        fake_calculator,
    )

    result = registry.execute_tool(
        tool_name="calculator",
        arguments='{"expression": "5 + 5"}',
        idempotency_key="lost_lease_001",
    )

    assert "lease was lost" in result.lower()

    operation = isolated_idempotency_store.lookup(
        "lost_lease_001"
    )

    assert operation["status"] == "recovery_required"
    assert operation["result"] is None


def test_expired_lease_during_approval_prevents_execution(
    isolated_idempotency_store,
    monkeypatch,
):
    execution_count = 0

    def fake_send_message(recipient, message):
        nonlocal execution_count
        execution_count += 1
        return "SIMULATION ONLY: Message processed."

    monkeypatch.setattr(
        registry.TOOL_REGISTRY["send_message"],
        "function",
        fake_send_message,
    )

    policy = ToolPolicy(
        allowed_permissions=frozenset({"message:send"})
    )

    def approve_after_lease_expiry(tool_name, arguments):
        assert isolated_idempotency_store.expire_lease(
            "approval_lease_expired_001"
        )
        return True

    result = registry.execute_tool(
        tool_name="send_message",
        arguments=(
            '{"recipient":"test@example.com",'
            '"message":"Hello"}'
        ),
        policy=policy,
        approval_callback=approve_after_lease_expiry,
        idempotency_key="approval_lease_expired_001",
    )

    assert "Recovery required" in result
    assert execution_count == 0

    operation = isolated_idempotency_store.lookup(
        "approval_lease_expired_001"
    )

    assert operation["status"] == "recovery_required"
    assert operation["result"] is None


# ---------------------------------------------------------
# Approval and idempotency interaction
# ---------------------------------------------------------

def test_duplicate_request_does_not_trigger_second_approval(
    isolated_idempotency_store,
    monkeypatch,
):
    tool = registry.TOOL_REGISTRY["send_message"]

    approval_count = 0
    execution_count = 0
    duplicate_result = None

    def fake_send_message(recipient, message):
        nonlocal execution_count
        execution_count += 1
        return "SIMULATION ONLY: Message processed."

    monkeypatch.setattr(
        tool,
        "function",
        fake_send_message,
    )

    policy = ToolPolicy(
        allowed_permissions=frozenset({"message:send"})
    )

    def approve_action(tool_name, arguments):
        nonlocal approval_count, duplicate_result

        approval_count += 1

        operation = isolated_idempotency_store.lookup(
            "duplicate_approval_001"
        )
        assert operation["status"] == "in_progress"

        duplicate_result = registry.execute_tool(
            tool_name="send_message",
            arguments=(
                '{"recipient":"test@example.com",'
                '"message":"Hello"}'
            ),
            policy=policy,
            approval_callback=approve_action,
            idempotency_key="duplicate_approval_001",
        )

        return True

    first_result = registry.execute_tool(
        tool_name="send_message",
        arguments=(
            '{"recipient":"test@example.com",'
            '"message":"Hello"}'
        ),
        policy=policy,
        approval_callback=approve_action,
        idempotency_key="duplicate_approval_001",
    )

    assert "SIMULATION ONLY" in first_result
    assert "already in progress" in duplicate_result
    assert approval_count == 1
    assert execution_count == 1


def test_rejected_approval_cancels_idempotent_operation(
    isolated_idempotency_store,
    monkeypatch,
):
    tool = registry.TOOL_REGISTRY["send_message"]

    execution_count = 0
    approval_count = 0

    def fake_send_message(recipient, message):
        nonlocal execution_count
        execution_count += 1
        return "SIMULATION ONLY: Message processed."

    monkeypatch.setattr(
        tool,
        "function",
        fake_send_message,
    )

    policy = ToolPolicy(
        allowed_permissions=frozenset({"message:send"})
    )

    def reject_action(tool_name, arguments):
        nonlocal approval_count
        approval_count += 1
        return False

    result = registry.execute_tool(
        tool_name="send_message",
        arguments=(
            '{"recipient":"test@example.com",'
            '"message":"Hello"}'
        ),
        policy=policy,
        approval_callback=reject_action,
        idempotency_key="rejected_approval_001",
    )

    assert "cancelled by user" in result.lower()

    operation = isolated_idempotency_store.lookup(
        "rejected_approval_001"
    )

    assert operation["status"] == "cancelled"
    assert operation["result"] == "Tool execution cancelled by user."

    repeated_result = registry.execute_tool(
        tool_name="send_message",
        arguments=(
            '{"recipient":"test@example.com",'
            '"message":"Hello"}'
        ),
        policy=policy,
        approval_callback=reject_action,
        idempotency_key="rejected_approval_001",
    )

    assert "Previous execution was cancelled" in repeated_result
    assert approval_count == 1
    assert execution_count == 0


def test_approval_cannot_override_missing_authorization(
    isolated_idempotency_store,
    monkeypatch,
):
    execution_count = 0
    approval_count = 0

    def fake_send_message(recipient, message):
        nonlocal execution_count
        execution_count += 1
        return "SIMULATION ONLY: Message processed."

    monkeypatch.setattr(
        registry.TOOL_REGISTRY["send_message"],
        "function",
        fake_send_message,
    )

    policy = ToolPolicy(
        allowed_permissions=frozenset()
    )

    def approve_action(tool_name, arguments):
        nonlocal approval_count
        approval_count += 1
        return True

    result = registry.execute_tool(
        tool_name="send_message",
        arguments=(
            '{"recipient":"test@example.com",'
            '"message":"Hello"}'
        ),
        policy=policy,
        approval_callback=approve_action,
        idempotency_key="unauthorized_approval_001",
    )

    assert "Tool authorization error" in result
    assert approval_count == 0
    assert execution_count == 0

    operation = isolated_idempotency_store.lookup(
        "unauthorized_approval_001"
    )

    assert operation is None


# ---------------------------------------------------------
# Database persistence failures
# ---------------------------------------------------------

def test_database_lookup_failure_prevents_tool_execution(
    isolated_idempotency_store,
    monkeypatch,
):
    execution_count = 0

    def fake_calculator(expression):
        nonlocal execution_count
        execution_count += 1
        return "10"

    def failing_lookup(*args, **kwargs):
        raise SQLAlchemyError(
            "simulated database unavailable"
        )

    monkeypatch.setattr(
        registry.TOOL_REGISTRY["calculator"],
        "function",
        fake_calculator,
    )
    monkeypatch.setattr(
        isolated_idempotency_store,
        "lookup",
        failing_lookup,
    )

    result = registry.execute_tool(
        "calculator",
        '{"expression":"5 + 5"}',
        idempotency_key="db_lookup_failure_001",
    )

    assert "Idempotency persistence error" in result
    assert execution_count == 0


def test_database_claim_failure_prevents_tool_execution(
    isolated_idempotency_store,
    monkeypatch,
):
    execution_count = 0

    def fake_calculator(expression):
        nonlocal execution_count
        execution_count += 1
        return "10"

    def failing_claim(*args, **kwargs):
        raise SQLAlchemyError(
            "simulated database unavailable"
        )

    monkeypatch.setattr(
        registry.TOOL_REGISTRY["calculator"],
        "function",
        fake_calculator,
    )
    monkeypatch.setattr(
        isolated_idempotency_store,
        "claim",
        failing_claim,
    )

    result = registry.execute_tool(
        "calculator",
        '{"expression":"5 + 5"}',
        idempotency_key="db_claim_failure_001",
    )

    assert "Idempotency persistence error" in result
    assert execution_count == 0


def test_database_finalization_failure_reports_uncertain_outcome(
    isolated_idempotency_store,
    monkeypatch,
):
    execution_count = 0

    def fake_calculator(expression):
        nonlocal execution_count
        execution_count += 1
        return "10"

    def failing_finish(*args, **kwargs):
        raise SQLAlchemyError(
            "simulated database unavailable"
        )

    monkeypatch.setattr(
        registry.TOOL_REGISTRY["calculator"],
        "function",
        fake_calculator,
    )
    monkeypatch.setattr(
        isolated_idempotency_store,
        "finish",
        failing_finish,
    )

    result = registry.execute_tool(
        "calculator",
        '{"expression":"5 + 5"}',
        idempotency_key="db_finish_failure_001",
    )

    assert execution_count == 1
    assert "uncertain" in result.lower()


def test_uncertain_execution_requires_recovery_and_is_not_reexecuted(
    isolated_idempotency_store,
    monkeypatch,
):
    execution_count = 0

    def fake_calculator(expression):
        nonlocal execution_count
        execution_count += 1
        return "10"

    def failing_finish(*args, **kwargs):
        raise SQLAlchemyError(
            "simulated database unavailable"
        )

    monkeypatch.setattr(
        registry.TOOL_REGISTRY["calculator"],
        "function",
        fake_calculator,
    )
    monkeypatch.setattr(
        isolated_idempotency_store,
        "finish",
        failing_finish,
    )

    idempotency_key = "crash_recovery_test_001"

    # Execute the operation.
    result = registry.execute_tool(
        "calculator",
        '{"expression":"5 + 5"}',
        idempotency_key=idempotency_key,
    )

    assert execution_count == 1
    assert "uncertain" in result.lower()

    # The operation remains in progress because finalization failed.
    operation = isolated_idempotency_store.lookup(
        idempotency_key
    )

    assert operation is not None
    assert operation["status"] == "in_progress"

    # Simulate the lease expiring and run recovery.
    assert isolated_idempotency_store.expire_lease(
        idempotency_key
    )

    isolated_idempotency_store.recover_expired_operations()

    operation = isolated_idempotency_store.lookup(
        idempotency_key
    )

    assert operation["status"] == "recovery_required"

    # A repeated request must not execute the tool again.
    retry_result = registry.execute_tool(
        "calculator",
        '{"expression":"5 + 5"}',
        idempotency_key=idempotency_key,
    )

    assert execution_count == 1
    assert "recovery" in retry_result.lower()


# ---------------------------------------------------------
# Reconciliation helpers and tests
# ---------------------------------------------------------

def create_recovery_required_operation(
    store,
    idempotency_key,
    tool_name="calculator",
    arguments=None,
):
    if arguments is None:
        arguments = {"expression": "10 + 5"}

    claim = store.claim(
        idempotency_key,
        tool_name,
        arguments,
    )

    assert claim["status"] == "new"

    assert store.expire_lease(idempotency_key)

    store.recover_expired_operations()

    operation = store.lookup(idempotency_key)

    assert operation["status"] == "recovery_required"

    return operation


def test_reconciled_completed_operation_is_not_executed_again(
    isolated_idempotency_store,
    monkeypatch,
):
    execution_count = 0

    def fake_calculator(expression):
        nonlocal execution_count
        execution_count += 1
        return f"result:{expression}"

    monkeypatch.setattr(
        registry.TOOL_REGISTRY["calculator"],
        "function",
        fake_calculator,
    )

    idempotency_key = "reconciled_completed_001"

    create_recovery_required_operation(
        isolated_idempotency_store,
        idempotency_key,
    )

    isolated_idempotency_store.reconcile_operation(
        idempotency_key=idempotency_key,
        decision="completed",
        evidence="External evidence confirms successful execution.",
        reconciled_by="test_operator",
        reconciled_result="Verified result from external evidence.",
    )

    result = registry.execute_tool(
        tool_name="calculator",
        arguments='{"expression": "10 + 5"}',
        idempotency_key=idempotency_key,
    )

    operation = isolated_idempotency_store.lookup(
        idempotency_key
    )

    assert execution_count == 0
    assert result == operation["result"]
    assert operation["status"] == "completed"


def test_reconciled_failed_operation_is_not_executed_again(
    isolated_idempotency_store,
    monkeypatch,
):
    execution_count = 0

    def fake_calculator(expression):
        nonlocal execution_count
        execution_count += 1
        return f"result:{expression}"

    monkeypatch.setattr(
        registry.TOOL_REGISTRY["calculator"],
        "function",
        fake_calculator,
    )

    idempotency_key = "reconciled_failed_001"

    create_recovery_required_operation(
        isolated_idempotency_store,
        idempotency_key,
    )

    isolated_idempotency_store.reconcile_operation(
        idempotency_key=idempotency_key,
        decision="failed",
        evidence="External evidence confirms that execution failed.",
        reconciled_by="test_operator",
    )

    result = registry.execute_tool(
        tool_name="calculator",
        arguments='{"expression": "10 + 5"}',
        idempotency_key=idempotency_key,
    )

    operation = isolated_idempotency_store.lookup(
        idempotency_key
    )

    assert operation["status"] == "failed"
    assert "Automatic re-execution is blocked" in result
    assert execution_count == 0


def test_reconciled_operation_rejects_different_arguments(
    isolated_idempotency_store,
    monkeypatch,
):
    execution_count = 0

    def fake_calculator(expression):
        nonlocal execution_count
        execution_count += 1
        return f"result:{expression}"

    monkeypatch.setattr(
        registry.TOOL_REGISTRY["calculator"],
        "function",
        fake_calculator,
    )

    idempotency_key = "reconciled_arguments_001"

    create_recovery_required_operation(
        isolated_idempotency_store,
        idempotency_key,
        arguments={"expression": "10 + 5"},
    )

    isolated_idempotency_store.reconcile_operation(
        idempotency_key=idempotency_key,
        decision="completed",
        evidence="External evidence confirms successful execution.",
        reconciled_by="test_operator",
        reconciled_result="Verified result from external evidence.",
    )

    result = registry.execute_tool(
        tool_name="calculator",
        arguments='{"expression": "20 + 5"}',
        idempotency_key=idempotency_key,
    )

    assert "Idempotency conflict" in result
    assert execution_count == 0


def test_reconciliation_does_not_bypass_authorization(
    isolated_idempotency_store,
    monkeypatch,
):
    execution_count = 0

    def fake_calculator(expression):
        nonlocal execution_count
        execution_count += 1
        return f"result:{expression}"

    monkeypatch.setattr(
        registry.TOOL_REGISTRY["calculator"],
        "function",
        fake_calculator,
    )

    idempotency_key = "reconciled_authorization_001"

    create_recovery_required_operation(
        isolated_idempotency_store,
        idempotency_key,
    )

    isolated_idempotency_store.reconcile_operation(
        idempotency_key=idempotency_key,
        decision="completed",
        evidence="External evidence confirms successful execution.",
        reconciled_by="test_operator",
        reconciled_result="Verified result from external evidence.",
    )

    unauthorized_policy = ToolPolicy(
        allowed_permissions=frozenset()
    )

    result = registry.execute_tool(
        tool_name="calculator",
        arguments='{"expression": "10 + 5"}',
        policy=unauthorized_policy,
        idempotency_key=idempotency_key,
    )

    assert "Tool authorization error" in result
    assert execution_count == 0
