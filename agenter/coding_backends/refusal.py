"""Shared refusal tool and detection logic for all backends.

This module provides a unified approach to handling LLM refusals across
all backends. Instead of each backend implementing its own refusal logic,
they can use the shared RefusalDetector and helper functions.

Usage:
    class MyBackend(RefusalDetector):
        async def execute(self, prompt: str):
            # Use self._capture_refusal() when refusal detected
            # Use self.refusal() to retrieve captured refusal
            pass

    # Or use the shared REFUSAL_TOOL directly:
    from .refusal import REFUSAL_TOOL
    all_tools = [REFUSAL_TOOL, *extra_tools]
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from ..data_models import ToolResult
from ..tools import FunctionTool

if TYPE_CHECKING:
    from ..data_models import RefusalMessage

# Refusal tool schema - backends convert to their native format
# (Anthropic tool format, MCP tool, etc.)
REFUSAL_TOOL_NAME = "Refusal"
REFUSAL_TOOL_DESCRIPTION = (
    "Signal that you cannot complete the request due to safety, policy, "
    "or capability limitations. Use this instead of silently failing."
)
REFUSAL_TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "reason": {
            "type": "string",
            "description": "Why you cannot proceed with this request",
        },
        "category": {
            "type": "string",
            "enum": ["safety", "policy", "capability"],
            "description": "Type of limitation preventing completion",
        },
    },
    "required": ["reason"],
}

# Instructions to include in system prompt so LLM knows about refusal tool
REFUSAL_INSTRUCTIONS = """\
## Refusal Tool
If you cannot complete this request due to safety, policy, or capability limitations, \
you MUST call the Refusal tool with:
- reason: Clear explanation of why you cannot proceed
- category: One of "safety", "policy", or "capability"

Do NOT silently refuse or return incomplete results. Always signal refusal explicitly."""


def _refusal_executor(args: dict) -> ToolResult:
    """Execute the refusal tool. Returns acknowledgment."""
    return ToolResult(output="Refusal acknowledged", success=True)


# Shared refusal tool instance - use this in backends
REFUSAL_TOOL = FunctionTool(
    name=REFUSAL_TOOL_NAME,
    description=REFUSAL_TOOL_DESCRIPTION,
    input_schema=REFUSAL_TOOL_SCHEMA,
    func=_refusal_executor,
)


class RefusalDetector:
    """Provides refusal state management for backends.

    Backends inherit this to get standardized refusal handling:
    - _reset_refusal(): Call in connect() and disconnect()
    - _capture_refusal(): Call when refusal is detected
    - refusal(): Returns captured refusal (required by protocol)

    Example:
        class MyBackend(RefusalDetector):
            def __init__(self):
                self._refusal = None  # Initialize state

            async def connect(self, cwd: str, ...):
                self._reset_refusal()
                ...

            async def execute(self, prompt: str):
                ...
                if is_refusal:
                    msg = self._capture_refusal(reason, category)
                    yield msg
                ...

            async def disconnect(self):
                self._reset_refusal()
    """

    _refusal: RefusalMessage | None

    def _reset_refusal(self) -> None:
        """Reset refusal state. Call in connect() and disconnect()."""
        self._refusal = None

    def _capture_refusal(
        self,
        reason: str,
        category: Literal["safety", "policy", "capability"] | None = None,
    ) -> RefusalMessage:
        """Capture a refusal and return the message for yielding.

        Args:
            reason: Why the LLM cannot proceed.
            category: Type of limitation (safety, policy, capability).

        Returns:
            RefusalMessage that can be yielded from execute().
        """
        from ..data_models import RefusalMessage

        self._refusal = RefusalMessage(reason=reason, category=category)
        return self._refusal

    def refusal(self) -> RefusalMessage | None:
        """Return refusal if LLM explicitly refused the request.

        Returns:
            RefusalMessage with reason and category if LLM called the Refusal tool,
            None otherwise.
        """
        return self._refusal


def parse_refusal_from_tool_call(
    tool_name: str,
    args: dict[str, Any],
) -> RefusalMessage | None:
    """Detect refusal from a tool call.

    Works with various tool naming conventions:
    - "Refusal" (direct tool name)
    - "mcp__server__Refusal" (MCP-style prefixed)
    - Any tool ending with "__Refusal"

    Args:
        tool_name: Name of the tool being called.
        args: Tool arguments (should contain "reason", optionally "category").

    Returns:
        RefusalMessage if this is a refusal tool call, None otherwise.
    """
    # Match direct name or MCP-prefixed name
    if tool_name != REFUSAL_TOOL_NAME and not tool_name.endswith(f"__{REFUSAL_TOOL_NAME}"):
        return None

    from ..data_models import RefusalMessage

    reason = args.get("reason", "Request refused")
    category = args.get("category")

    # Validate category if provided
    if category is not None and category not in ("safety", "policy", "capability"):
        category = None

    return RefusalMessage(reason=reason, category=category)
