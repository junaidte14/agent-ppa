import json
from uuid import uuid4

import agent
import tools.registry as registry

from sqlalchemy import delete, select

from database.connection import SessionLocal
from database.models import Operation, OperationReconciliation
from services.idempotency_service import IdempotencyService


class MultiToolFakeLLM:
    def __init__(self, calculator_call_id, analyzer_call_id):
        self.calls = 0
        self.calculator_call_id = calculator_call_id
        self.analyzer_call_id = analyzer_call_id

    def complete_with_tools(self, messages, tools):
        self.calls += 1

        if self.calls == 1:
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": self.calculator_call_id,
                        "type": "function",
                        "function": {
                            "name": "calculator",
                            "arguments": json.dumps({
                                "expression": "150 + 250"
                            }),
                        },
                    }
                ],
            }

        if self.calls == 2:
            tool_messages = [
                message
                for message in messages
                if message.get("role") == "tool"
            ]

            assert len(tool_messages) == 1
            assert (
                tool_messages[0]["tool_call_id"]
                == self.calculator_call_id
            )
            assert tool_messages[0]["content"] == "400"

            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": self.analyzer_call_id,
                        "type": "function",
                        "function": {
                            "name": "analyze_text",
                            "arguments": json.dumps({
                                "text": "400"
                            }),
                        },
                    }
                ],
            }

        if self.calls == 3:
            tool_messages = [
                message
                for message in messages
                if message.get("role") == "tool"
            ]

            assert len(tool_messages) == 2
            assert (
                tool_messages[0]["tool_call_id"]
                == self.calculator_call_id
            )
            assert (
                tool_messages[1]["tool_call_id"]
                == self.analyzer_call_id
            )
            assert tool_messages[0]["content"] == "400"

            return {
                "role": "assistant",
                "content": (
                    "The calculation result is 400. "
                    "The text analyzer processed the result."
                ),
                "tool_calls": [],
            }

        raise AssertionError("Unexpected additional LLM call")


def cleanup_operations(idempotency_keys):
    with SessionLocal() as session:
        with session.begin():
            operation_ids = session.scalars(
                select(Operation.id).where(
                    Operation.idempotency_key.in_(idempotency_keys)
                )
            ).all()

            if operation_ids:
                session.execute(
                    delete(OperationReconciliation).where(
                        OperationReconciliation.operation_id.in_(
                            operation_ids
                        )
                    )
                )

                session.execute(
                    delete(Operation).where(
                        Operation.id.in_(operation_ids)
                    )
                )


def test_agent_executes_sequential_multi_tool_workflow(monkeypatch):
    store = IdempotencyService()

    calculator_call_id = f"call_calculator_{uuid4().hex}"
    analyzer_call_id = f"call_analyzer_{uuid4().hex}"

    idempotency_keys = [
        calculator_call_id,
        analyzer_call_id,
    ]

    monkeypatch.setattr(
        registry,
        "idempotency_store",
        store,
    )

    execution_counts = {
        "calculator": 0,
        "analyze_text": 0,
    }

    calculator_tool = registry.TOOL_REGISTRY["calculator"]
    analyzer_tool = registry.TOOL_REGISTRY["analyze_text"]

    def fake_calculator(expression):
        execution_counts["calculator"] += 1
        assert expression == "150 + 250"
        return "400"

    def fake_analyze_text(text):
        execution_counts["analyze_text"] += 1
        assert text == "400"
        return "Text analysis completed for: 400"

    monkeypatch.setattr(
        calculator_tool,
        "function",
        fake_calculator,
    )

    monkeypatch.setattr(
        analyzer_tool,
        "function",
        fake_analyze_text,
    )

    try:
        llm = MultiToolFakeLLM(
            calculator_call_id=calculator_call_id,
            analyzer_call_id=analyzer_call_id,
        )

        messages = [
            {
                "role": "system",
                "content": "Test agent",
            },
            {
                "role": "user",
                "content": (
                    "Calculate 150 + 250 and analyze the result."
                ),
            },
        ]

        answer = agent.run_agent_turn(
            llm=llm,
            messages=messages,
        )

        assert answer == (
            "The calculation result is 400. "
            "The text analyzer processed the result."
        )

        assert llm.calls == 3

        assert execution_counts == {
            "calculator": 1,
            "analyze_text": 1,
        }

        tool_messages = [
            message
            for message in messages
            if message.get("role") == "tool"
        ]

        assert len(tool_messages) == 2

        assert (
            tool_messages[0]["tool_call_id"]
            == calculator_call_id
        )
        assert (
            tool_messages[1]["tool_call_id"]
            == analyzer_call_id
        )

        assert tool_messages[0]["content"] == "400"

        calculator_operation = store.lookup(
            calculator_call_id,
            "calculator",
            {"expression": "150 + 250"},
        )

        analyzer_operation = store.lookup(
            analyzer_call_id,
            "analyze_text",
            {"text": "400"},
        )

        assert calculator_operation["status"] == "completed"
        assert analyzer_operation["status"] == "completed"

    finally:
        cleanup_operations(idempotency_keys)