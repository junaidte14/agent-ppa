
import json
from uuid import uuid4

import agent
import tools.registry as registry

from database.connection import SessionLocal
from database.models import Operation, OperationReconciliation
from sqlalchemy import delete, select

from services.idempotency_service import IdempotencyService


class FakeLLM:
    def __init__(self, tool_call_id):
        self.tool_call_id = tool_call_id
        self.calls = 0

    def complete_with_tools(self, messages, tools):
        self.calls += 1

        if self.calls == 1:
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": self.tool_call_id,
                        "type": "function",
                        "function": {
                            "name": "calculator",
                            "arguments": json.dumps({
                                "expression": "10 + 5"
                            }),
                        },
                    }
                ],
            }

        return {
            "role": "assistant",
            "content": "The result is 15.",
            "tool_calls": [],
        }


def test_agent_passes_tool_call_id_as_idempotency_key(
    monkeypatch,
):
    store = IdempotencyService()
    tool_call_id = f"call_test_{uuid4().hex}"

    monkeypatch.setattr(
        registry,
        "idempotency_store",
        store,
    )

    calculator_tool = registry.TOOL_REGISTRY["calculator"]
    execution_count = 0

    def fake_calculator(expression):
        nonlocal execution_count
        execution_count += 1
        return "15"

    monkeypatch.setattr(
        calculator_tool,
        "function",
        fake_calculator,
    )

    original_execute_tool = registry.execute_tool

    def tracked_execute_tool(*args, **kwargs):
        return original_execute_tool(*args, **kwargs)

    monkeypatch.setattr(
        agent,
        "execute_tool",
        tracked_execute_tool,
    )

    try:
        llm = FakeLLM(tool_call_id=tool_call_id)

        first_answer = agent.run_agent_turn(
            llm,
            [{"role": "system", "content": "Test agent"}],
        )

        second_answer = agent.run_agent_turn(
            llm,
            [{"role": "system", "content": "Test agent"}],
        )

        assert first_answer == "The result is 15."
        assert second_answer == "The result is 15."
        assert execution_count == 1

        stored_operation = store.lookup(
            tool_call_id,
            "calculator",
            {"expression": "10 + 5"},
        )

        assert stored_operation["status"] == "completed"

    finally:
        with SessionLocal() as session:
            with session.begin():
                operation_id = session.scalar(
                    select(Operation.id).where(
                        Operation.idempotency_key == tool_call_id
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
