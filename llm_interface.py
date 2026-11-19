from typing import Protocol, Any

class LLMClient(Protocol):
    """
    Standard interface for all LLM providers.

    Any provider adapter implementing this interface
    must provide a complete() method.
    """

    def complete(self, messages: list[dict[str, str]]) -> str:
        ...

    def complete_with_tools(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        ...