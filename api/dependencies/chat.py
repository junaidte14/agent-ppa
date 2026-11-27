from litellm_adapter import LiteLLMAdapter
from llm_interface import LLMClient

from tools.policy import DEFAULT_TOOL_POLICY, ToolPolicy
from tools.registry import TOOL_REGISTRY


def get_llm() -> LLMClient:
    return LiteLLMAdapter()


APPROVAL_REQUIRED_PERMISSIONS = frozenset(
    tool.required_permission
    for tool in TOOL_REGISTRY.values()
    if tool.requires_approval
)


WEB_TOOL_POLICY = ToolPolicy(
    allowed_permissions=frozenset(
        permission
        for permission in DEFAULT_TOOL_POLICY.allowed_permissions
        if permission not in APPROVAL_REQUIRED_PERMISSIONS
    )
)
