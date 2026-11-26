import json
from uuid import UUID
from typing import Any, Callable

from llm_interface import LLMClient
from tools.registry import TOOL_DEFINITIONS, execute_tool
from tools.policy import DEFAULT_TOOL_POLICY, ToolPolicy

MAX_TOOL_ROUNDS = 5

def _json_default(value: Any) -> str:
    if isinstance(value, UUID):
        return str(value)

    raise TypeError(
        f"Object of type {type(value).__name__} "
        "is not JSON serializable"
    )

def request_tool_approval(
    tool_name: str,
    arguments: dict[str, Any]
) -> bool:
    """
    Ask the human to approve a validated tool action.
    This callback is intended for the CLI.
    """

    print("\n" + "=" * 50)
    print("HUMAN APPROVAL REQUIRED")
    print("=" * 50)

    print(f"Tool: {tool_name}")
    print("Validated arguments:")

    print(
        json.dumps(
            arguments,
            indent=4,
            ensure_ascii=False,
            default=_json_default,
        )
    )

    print("=" * 50)

    decision = input(
        "Approve this action? (yes/no): "
    ).strip().lower()

    return decision in {"yes", "y"}

def run_agent_turn(
    llm: LLMClient,
    messages: list[dict[str, Any]],
    policy: ToolPolicy = DEFAULT_TOOL_POLICY,
    approval_callback: Callable[
        [str, dict[str, Any]], bool
    ] | None = request_tool_approval,
) -> str:
    """
    Run one user turn, allowing the LLM to call tools.

    The caller can supply a different permission policy and
    approval callback depending on the execution environment.
    """

    for round_number in range(MAX_TOOL_ROUNDS):
        
        # Step 1: Ask the LLM what to do.
        assistant_message = llm.complete_with_tools(
            messages=messages,
            tools=TOOL_DEFINITIONS
        )

        tool_calls = assistant_message.get("tool_calls", [])

        # Step 2: No tool requested: return the normal answer.
        if not tool_calls:
            content = assistant_message.get("content")

            if not isinstance(content, str):
                raise RuntimeError("LLM returned no final answer")

            messages.append(assistant_message)
            return content

        # Step 3: Preserve the assistant tool-call request.
        messages.append(assistant_message)

        if round_number == MAX_TOOL_ROUNDS - 1:
            raise RuntimeError("Maximum tool-call rounds exceeded")

        # Step 4: Execute each requested tool.
        for tool_call in tool_calls:
            try:
                tool_id = tool_call["id"]
                function = tool_call["function"]

                tool_name = function["name"]
                arguments = function["arguments"]

                if not isinstance(tool_id, str) or not tool_id.strip():
                    raise ValueError("Invalid tool call ID")

                if not isinstance(tool_name, str) or not tool_name.strip():
                    raise ValueError("Invalid tool name")

                if not isinstance(arguments, str):
                    raise ValueError(
                        "Tool arguments must be a JSON string"
                    )

            except (KeyError, TypeError, ValueError) as error:
                raise RuntimeError(
                    f"Malformed tool call received from LLM: {error}"
                ) from error

            print(
                f"[Agent] calling tool: {tool_name} "
                f"with arguments: {arguments}"
            )

            result = execute_tool(
                tool_name=tool_name,
                arguments=arguments,
                policy=policy,
                approval_callback=approval_callback,
                idempotency_key=tool_id
            )

            print(f"[Agent] Tool result: {result}")

            # Step 5: Send the tool result back to the LLM.
            messages.append({
                "role": "tool",
                "tool_call_id": tool_id,
                "name": tool_name,
                "content": result
            })

    raise RuntimeError(
        "Agent stopped without producing a final answer"
    )