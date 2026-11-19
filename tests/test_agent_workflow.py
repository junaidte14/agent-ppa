import json
import agent
import tools.registry as registry

from tools.idempotency import IdempotencyStore

class MultiToolFakeLLM:
    def __init__(self):
        self.calls = 0

    def complete_with_tools(self, messages, tools):
        self.calls += 1

        if self.calls == 1:
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_calculator_001",
                        "type": "function",
                        "function": {
                            "name": "calculator",
                            "arguments": json.dumps({
                                "expression": "150 + 250"
                            })
                        }
                    }
                ]
            }

        if self.calls == 2:
            # Verify that the first tool result reached the LLM.
            tool_messages = [
                message
                for message in messages
                if message.get("role") == "tool"
            ]

            assert len(tool_messages) == 1
            assert (
                tool_messages[0]["tool_call_id"]
                == "call_calculator_001"
            )
            assert tool_messages[0]["content"] == "400"

            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_analyzer_001",
                        "type": "function",
                        "function": {
                            "name": "analyze_text",
                            "arguments": json.dumps({
                                "text": "400"
                            })
                        }
                    }
                ]
            }

        if self.calls == 3:
            # Verify that both tool results reached the LLM.
            tool_messages = [
                message
                for message in messages
                if message.get("role") == "tool"
            ]

            assert len(tool_messages) == 2

            assert tool_messages[0]["tool_call_id"] == (
                "call_calculator_001"
            )

            assert tool_messages[1]["tool_call_id"] == (
                "call_analyzer_001"
            )

            assert tool_messages[0]["content"] == "400"

            return {
                "role": "assistant",
                "content": (
                    "The calculation result is 400. "
                    "The text analyzer processed the result."
                ),
                "tool_calls": []
            }

        raise AssertionError("Unexpected additional LLM call")


def test_agent_executes_sequential_multi_tool_workflow(
    tmp_path,
    monkeypatch
):
    store = IdempotencyStore(
        tmp_path / "workflow_test.db"
    )

    monkeypatch.setattr(
        registry,
        "idempotency_store",
        store
    )

    execution_counts = {
        "calculator": 0,
        "analyze_text": 0
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
        fake_calculator
    )

    monkeypatch.setattr(
        analyzer_tool,
        "function",
        fake_analyze_text
    )

    llm = MultiToolFakeLLM()

    messages = [
        {
            "role": "system",
            "content": "Test agent"
        },
        {
            "role": "user",
            "content": (
                "Calculate 150 + 250 and analyze the result."
            )
        }
    ]

    answer = agent.run_agent_turn(
        llm=llm,
        messages=messages
    )

    assert answer == (
        "The calculation result is 400. "
        "The text analyzer processed the result."
    )

    assert llm.calls == 3

    assert execution_counts == {
        "calculator": 1,
        "analyze_text": 1
    }

    tool_messages = [
        message
        for message in messages
        if message.get("role") == "tool"
    ]

    assert len(tool_messages) == 2

    assert tool_messages[0]["tool_call_id"] == (
        "call_calculator_001"
    )

    assert tool_messages[1]["tool_call_id"] == (
        "call_analyzer_001"
    )

    calculator_operation = store.lookup(
        "call_calculator_001",
        "calculator",
        {"expression": "150 + 250"}
    )

    analyzer_operation = store.lookup(
        "call_analyzer_001",
        "analyze_text",
        {"text": "400"}
    )

    assert calculator_operation["status"] == "completed"
    assert analyzer_operation["status"] == "completed"
