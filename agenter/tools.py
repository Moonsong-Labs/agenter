"""Tool abstraction for adding custom tools to the agent.

Uses the same format as Claude Agent SDK's @tool decorator.

Example:
    from agenter import tool, ToolResult

    @tool("search", "Search the web", {"query": str})
    async def search(args: dict) -> ToolResult:
        query = args["query"]
        results = await do_search(query)
        return ToolResult(output=results, success=True)
"""

from __future__ import annotations

import asyncio
import inspect
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import structlog

from .data_models import ToolError, ToolErrorCode, ToolResult

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger(__name__)


@runtime_checkable
class Tool(Protocol):
    """Protocol for custom tools.

    Custom tools must implement this protocol to be used with the SDK.

    Attributes:
        name: Unique identifier for the tool.
        description: Human-readable description of what the tool does.
        input_schema: JSON Schema defining the tool's input parameters.
    """

    name: str
    description: str
    input_schema: dict

    async def execute(self, inputs: dict) -> ToolResult:
        """Execute the tool with given inputs.

        Args:
            inputs: Dictionary of input parameters matching input_schema.

        Returns:
            ToolResult with output and success status.
        """
        ...


class FunctionTool:
    """Tool wrapping a function. Compatible with Claude Agent SDK style.

    This class wraps a regular or async function as a Tool that can be
    used with the SDK. The wrapped function can return various formats
    which will be normalized to ToolResult.

    Args:
        name: Unique identifier for the tool.
        description: Human-readable description of what the tool does.
        input_schema: JSON Schema defining the tool's input parameters.
        func: The function to wrap (can be sync or async).

    Example:
        def my_func(inputs: dict) -> str:
            return f"Hello, {inputs['name']}!"

        tool = FunctionTool(
            name="greet",
            description="Greet a user",
            input_schema={"type": "object", "properties": {"name": {"type": "string"}}},
            func=my_func,
        )
    """

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: dict,
        func: Callable,
    ) -> None:
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self._func = func

    async def execute(self, inputs: dict) -> ToolResult:
        """Execute the wrapped function.

        The function can return:
        - ToolResult: Used directly
        - tuple[str, bool]: Converted to ToolResult(output, success)
        - str: Converted to ToolResult(output=str, success=True)
        - dict: JSON-encoded and returned as successful ToolResult
        - Any other type: Converted to string

        Args:
            inputs: Input parameters for the function.

        Returns:
            ToolResult with the function's output.
        """
        try:
            if inspect.iscoroutinefunction(self._func):
                result = await self._func(inputs)
            else:
                result = await asyncio.to_thread(self._func, inputs)

            # Handle different return formats
            if isinstance(result, ToolResult):
                return result
            elif isinstance(result, str):
                return ToolResult(output=result, success=True)
            elif isinstance(result, dict):
                # MCP-style response
                import json

                return ToolResult(output=json.dumps(result), success=True)
            else:
                return ToolResult(output=str(result), success=True)
        except Exception as e:
            logger.exception("tool_execution_failed", tool_name=self.name)
            return ToolResult(
                output=f"Error: {e}",
                success=False,
                error=ToolError(code=ToolErrorCode.EXECUTION_ERROR, message=str(e)),
            )


def tool(
    name: str,
    description: str,
    input_schema: dict | None = None,
) -> Callable[[Callable], FunctionTool]:
    """Decorator to create a Tool from a function.

    Compatible with Claude Agent SDK style:
        @tool("greet", "Greet a user", {"name": str})
        async def greet(args):
            return f"Hello, {args['name']}!"

    Or with JSON schema:
        @tool(
            name="search",
            description="Search the web",
            input_schema={"type": "object", "properties": {"query": {"type": "string"}}}
        )
        async def search(inputs):
            return results, True
    """

    def decorator(func: Callable) -> FunctionTool:
        # Convert simple type hints to JSON schema if needed
        schema = input_schema or {}
        if schema and not schema.get("type"):
            # Convert {"name": str} to JSON schema
            schema = _types_to_schema(schema)

        return FunctionTool(
            name=name,
            description=description,
            input_schema=schema,
            func=func,
        )

    return decorator


def _types_to_schema(types: dict) -> dict:
    """Convert Python types to JSON schema using Pydantic.

    Supports all Pydantic-compatible types (Optional, Union, Enum, etc.).
    """
    from pydantic import create_model

    # Create fields definition for create_model
    # usage: name=(type, default) or (type, Field(...))
    # We assume all fields in the dict are required (no default)
    fields = {k: (v, ...) for k, v in types.items()}

    # Create dynamic model
    model = create_model("ToolInput", **fields)  # type: ignore[call-overload]

    # Generate schema
    schema = model.model_json_schema()

    # Clean up schema (remove title/description of the container)
    schema.pop("title", None)
    schema.pop("description", None)

    return schema
