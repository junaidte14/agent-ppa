
from typing import Any, Callable

from sqlalchemy.exc import SQLAlchemyError

from tools.base import Tool
from tools.policy import DEFAULT_TOOL_POLICY, ToolPolicy
from tools.audit import write_audit_event

from services.idempotency_service import (
    idempotency_service as idempotency_store,
)

from tools.calculator import calculator
from tools.date_time import get_current_datetime
from tools.text_analyzer import analyze_text
from tools.messaging import send_message

from tools.schemas import (
    CalculatorInput,
    DateTimeInput,
    TextAnalyzerInput,
    MessageInput,
)


# ---------------------------------------------------------
# Tool registration
# ---------------------------------------------------------

TOOLS = [
    Tool(
        name="calculator",
        description=(
            "Evaluate a mathematical expression accurately. "
            "Use this tool whenever the user asks for an "
            "arithmetic calculation."
        ),
        args_schema=CalculatorInput,
        function=calculator,
        required_permission="math:calculate",
    ),
    Tool(
        name="get_current_datetime",
        description=(
            "Get the current local date, time, "
            "timezone and weekday."
        ),
        args_schema=DateTimeInput,
        function=get_current_datetime,
        required_permission="system:read_time",
    ),
    Tool(
        name="analyze_text",
        description=(
            "Analyze text and calculate its character count, "
            "word count, line count and unique word count."
        ),
        args_schema=TextAnalyzerInput,
        function=analyze_text,
        required_permission="text:analyze",
    ),
    Tool(
        name="send_message",
        description=(
            "Simulate sending a message to the specified recipient "
            "with the supplied message content."
        ),
        args_schema=MessageInput,
        function=send_message,
        required_permission="message:send",
        requires_approval=True,
    ),
]

TOOL_REGISTRY = {
    tool.name: tool for tool in TOOLS
}

TOOL_DEFINITIONS = [
    tool.to_llm_definition() for tool in TOOLS
]


# ---------------------------------------------------------
# Existing operation response handling
# ---------------------------------------------------------

def _existing_operation_result(
    status: str,
    existing: dict[str, Any],
) -> str:
    """Translate an existing idempotency state into a safe result."""

    if status == "completed":
        return existing["result"]

    if status == "in_progress":
        return (
            "Idempotency notice: This operation "
            "is already in progress."
        )

    if status == "failed":
        return (
            "Previous execution failed. "
            "Automatic re-execution is blocked. "
            f"Previous result: {existing['result']}"
        )

    if status == "recovery_required":
        return (
            "Recovery required: The previous operation "
            "has an uncertain execution outcome. "
            "Manual inspection is required. "
            "Automatic re-execution is blocked."
        )

    if status == "cancelled":
        return (
            "Previous execution was cancelled. "
            "This idempotency key cannot be reused."
        )

    return (
        "Idempotency conflict: This key was "
        "already used for a different operation."
    )


# ---------------------------------------------------------
# Persistence and recovery helpers
# ---------------------------------------------------------

def _cancel_claim(
    idempotency_key: str,
    lease_token: str,
    result: str,
) -> bool:
    """Attempt to cancel a claimed operation."""

    try:
        return idempotency_store.cancel(
            idempotency_key=idempotency_key,
            lease_token=lease_token,
            result=result,
        )
    except SQLAlchemyError:
        return False


def _recover_expired_claim() -> bool:
    """
    Attempt to transition expired in-progress operations
    to recovery_required.

    Returns False if recovery persistence fails.
    """

    try:
        idempotency_store.recover_expired_operations()
        return True
    except SQLAlchemyError:
        return False


def _finalization_failure_message() -> str:
    return (
        "Operation execution returned a result, but the database "
        "could not confirm finalization. The execution outcome is "
        "uncertain from the operation store's perspective. "
        "Manual recovery is required."
    )


# ---------------------------------------------------------
# Tool execution
# ---------------------------------------------------------

def execute_tool(
    tool_name: str,
    arguments: str,
    policy: ToolPolicy = DEFAULT_TOOL_POLICY,
    approval_callback: Callable[
        [str, dict[str, Any]], bool
    ] | None = None,
    idempotency_key: str | None = None,
) -> str:

    tool = TOOL_REGISTRY.get(tool_name)

    if tool is None:
        write_audit_event(
            "tool_request",
            tool=tool_name,
            outcome="unknown_tool",
        )
        return f"Tool Error: Unknown tool '{tool_name}'"

    write_audit_event(
        "tool_request",
        tool=tool_name,
        permission=tool.required_permission,
        argument_fields=list(
            tool.args_schema.model_fields.keys()
        ),
    )

    # -----------------------------------------------------
    # 1. Authorization must always happen first.
    # -----------------------------------------------------

    if not policy.is_allowed(tool.required_permission):
        write_audit_event(
            "authorization",
            tool=tool.name,
            permission=tool.required_permission,
            outcome="denied",
        )

        return (
            "Tool authorization error: "
            f"Permission '{tool.required_permission}' "
            "is not allowed."
        )

    write_audit_event(
        "authorization",
        tool=tool.name,
        permission=tool.required_permission,
        outcome="allowed",
    )

    # -----------------------------------------------------
    # 2. Original non-idempotent execution path.
    # -----------------------------------------------------

    if idempotency_key is None:
        try:
            result = tool.execute(
                arguments,
                approval_callback=approval_callback,
            )
        except Exception as error:
            result = f"Tool execution error: {error}"

    else:
        try:
            # -------------------------------------------------
            # 3. Validate arguments before persistence.
            # -------------------------------------------------

            validated_arguments = tool.validate_arguments(
                arguments
            )

            # -------------------------------------------------
            # 4. Look up an existing operation.
            # -------------------------------------------------

            existing = idempotency_store.lookup(
                idempotency_key,
                tool_name,
                validated_arguments,
            )

            if existing is not None:
                result = _existing_operation_result(
                    existing["status"],
                    existing,
                )

            # -------------------------------------------------
            # 5. Approval handler must exist when required.
            # -------------------------------------------------

            elif (
                tool.requires_approval
                and approval_callback is None
            ):
                result = (
                    "Tool approval error: No approval handler "
                    "configured. Action is blocked."
                )

            else:
                # -------------------------------------------------
                # 6. Atomically claim the operation.
                # -------------------------------------------------

                claim = idempotency_store.claim(
                    idempotency_key,
                    tool_name,
                    validated_arguments,
                )

                if claim["status"] != "new":
                    result = _existing_operation_result(
                        claim["status"],
                        claim,
                    )

                else:
                    lease_token = claim["lease_token"]

                    # ---------------------------------------------
                    # 7. Request approval after claiming.
                    # ---------------------------------------------

                    try:
                        approved = tool.request_approval(
                            validated_arguments,
                            approval_callback,
                        )

                    except Exception as error:
                        approval_error = (
                            f"Tool approval error: {error}"
                        )

                        cancelled = _cancel_claim(
                            idempotency_key,
                            lease_token,
                            approval_error,
                        )

                        if cancelled:
                            result = approval_error
                        else:
                            _recover_expired_claim()
                            result = (
                                "Recovery required: Approval handling "
                                "failed and the operation could not be "
                                "cancelled. Manual inspection is required."
                            )

                    else:
                        # -----------------------------------------
                        # 8. Handle approval rejection.
                        # -----------------------------------------

                        if not approved:
                            cancelled = _cancel_claim(
                                idempotency_key,
                                lease_token,
                                "Tool execution cancelled by user.",
                            )

                            if cancelled:
                                result = (
                                    "Tool execution cancelled by user."
                                )
                            else:
                                _recover_expired_claim()
                                result = (
                                    "Recovery required: The operation "
                                    "could not be cancelled. "
                                    "Manual inspection is required."
                                )

                        else:
                            # -------------------------------------
                            # 9. Renew lease after approval.
                            # -------------------------------------

                            renewed = idempotency_store.renew_lease(
                                idempotency_key=idempotency_key,
                                lease_token=lease_token,
                            )

                            if not renewed:
                                recovery_succeeded = (
                                    _recover_expired_claim()
                                )

                                result = (
                                    "Recovery required: The operation "
                                    "lease expired or was lost while "
                                    "waiting for approval. The tool "
                                    "was not executed."
                                )

                                if not recovery_succeeded:
                                    result += (
                                        " Recovery persistence also "
                                        "failed; inspect the operation "
                                        "state before retrying."
                                    )

                            else:
                                # ---------------------------------
                                # 10. Execute the validated tool.
                                # ---------------------------------

                                try:
                                    execution_result = (
                                        tool.execute_validated(
                                            validated_arguments
                                        )
                                    )

                                except Exception as error:
                                    execution_error = (
                                        f"Tool execution error: {error}"
                                    )

                                    # -----------------------------
                                    # 11. Persist execution failure.
                                    # -----------------------------

                                    try:
                                        finalized = (
                                            idempotency_store.finish(
                                                idempotency_key=(
                                                    idempotency_key
                                                ),
                                                lease_token=lease_token,
                                                result=execution_error,
                                                status="failed",
                                            )
                                        )

                                    except SQLAlchemyError:
                                        result = (
                                            "Execution outcome uncertain: "
                                            "The tool reported an error, "
                                            "but the database was "
                                            "unavailable while recording "
                                            "the failure. Manual recovery "
                                            "is required."
                                        )

                                    else:
                                        if finalized:
                                            result = execution_error
                                        else:
                                            result = (
                                                "Tool execution failed, "
                                                "but its lease was lost "
                                                "before the failure could "
                                                "be recorded. Manual "
                                                "recovery is required."
                                            )

                                else:
                                    # ---------------------------------
                                    # 12. Persist successful execution.
                                    # ---------------------------------

                                    try:
                                        finalized = (
                                            idempotency_store.finish(
                                                idempotency_key=(
                                                    idempotency_key
                                                ),
                                                lease_token=lease_token,
                                                result=execution_result,
                                                status="completed",
                                            )
                                        )

                                    except SQLAlchemyError:
                                        result = (
                                            _finalization_failure_message()
                                        )

                                    else:
                                        if finalized:
                                            result = execution_result
                                        else:
                                            result = (
                                                "Operation execution "
                                                "returned a result, but "
                                                "its lease was lost before "
                                                "finalization. The "
                                                "execution outcome may "
                                                "be uncertain. Manual "
                                                "recovery is required."
                                            )

        except SQLAlchemyError:
            result = (
                "Idempotency persistence error: The PostgreSQL "
                "database operation failed. The tool was not "
                "confirmed as completed. Please inspect the "
                "operation state before retrying."
            )

        except Exception as error:
            result = f"Tool execution error: {error}"

    # -----------------------------------------------------
    # 13. Record the final audit outcome.
    # -----------------------------------------------------

    if result == "Tool execution cancelled by user.":
        outcome = "cancelled"

    elif result.startswith("Tool approval error:"):
        outcome = "approval_error"

    elif result.startswith("Tool execution error:"):
        outcome = "execution_error"

    elif result.startswith("Idempotency persistence error:"):
        outcome = "persistence_error"

    elif result.startswith("Recovery required:"):
        outcome = "recovery_required"

    elif result.startswith("Execution outcome uncertain:"):
        outcome = "execution_uncertain"

    elif result.startswith(
        "Operation execution returned a result,"
    ):
        outcome = "execution_uncertain"

    elif result.startswith("Tool execution failed,"):
        outcome = "execution_uncertain"

    elif result.startswith("Idempotency notice:"):
        outcome = "already_in_progress"

    elif result.startswith("Previous execution failed."):
        outcome = "previously_failed"

    elif result.startswith("Previous execution was cancelled."):
        outcome = "cancelled"

    elif result.startswith("Idempotency conflict:"):
        outcome = "idempotency_conflict"

    else:
        outcome = "completed"

    write_audit_event(
        "tool_execution",
        tool=tool.name,
        permission=tool.required_permission,
        outcome=outcome,
    )

    return result
