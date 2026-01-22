"""Tool-related types for the SDK.

This module contains types for tool execution results and error handling.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolErrorCode(str, Enum):
    """Standardized error codes for tool failures."""

    FILE_NOT_FOUND = "file_not_found"
    PATH_SECURITY = "path_security"
    INVALID_INPUT = "invalid_input"
    STRING_NOT_FOUND = "string_not_found"
    IO_ERROR = "io_error"
    UNKNOWN_TOOL = "unknown_tool"
    NOT_A_DIRECTORY = "not_a_directory"
    EXECUTION_ERROR = "execution_error"


class ToolError(BaseModel):
    """Structured error information for tool failures.

    Args:
        code: Machine-readable error code from ToolErrorCode.
        message: Human-readable error description.
    """

    code: ToolErrorCode
    message: str


class ToolResult(BaseModel):
    """Result from tool execution.

    This is the return type for all tool execute() methods and is also
    used as a BackendMessage when streaming tool results.

    Args:
        output: The tool's output message or data.
        success: Whether the tool executed successfully.
        tool_name: Name of the tool (set by backend when streaming).
        error: Optional structured error information.
        metadata: Optional additional metadata about the execution.

    Example:
        # Successful result
        return ToolResult(output="File created successfully", success=True)

        # Failed result with structured error
        return ToolResult(
            output="File not found: config.py",
            success=False,
            error=ToolError(code=ToolErrorCode.FILE_NOT_FOUND, message="config.py"),
        )

        # Using the factory method for errors
        return ToolResult.from_error(ToolErrorCode.FILE_NOT_FOUND, "config.py")
    """

    type: Literal["tool_result"] = "tool_result"
    output: str
    success: bool
    tool_name: str | None = None  # Set by backend when yielding as message
    error: ToolError | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_error(
        cls,
        code: ToolErrorCode,
        message: str,
        *,
        tool_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResult:
        """Create a failed ToolResult with structured error information.

        This factory method reduces boilerplate when creating error results.

        Args:
            code: Machine-readable error code from ToolErrorCode.
            message: Human-readable error description.
            tool_name: Optional tool name (for streaming context).
            metadata: Optional additional metadata.

        Returns:
            A ToolResult with success=False and structured error.

        Example:
            return ToolResult.from_error(ToolErrorCode.FILE_NOT_FOUND, "config.py")
            # Equivalent to:
            # return ToolResult(
            #     output="Error: config.py",
            #     success=False,
            #     error=ToolError(code=ToolErrorCode.FILE_NOT_FOUND, message="config.py"),
            # )
        """
        return cls(
            output=f"Error: {message}",
            success=False,
            tool_name=tool_name,
            error=ToolError(code=code, message=message),
            metadata=metadata or {},
        )
