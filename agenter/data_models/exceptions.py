"""Exceptions for Agenter.

This module defines a hierarchy of exceptions that provide structured error
handling throughout the SDK. All exceptions inherit from AgenterError.

Example:
    from agenter.exceptions import ToolExecutionError

    try:
        result = await tool.execute(inputs)
    except ToolExecutionError as e:
        print(f"Tool {e.tool_name} failed: {e.message}")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class AgenterError(Exception):
    """Base exception for all SDK errors.

    All exceptions raised by the SDK inherit from this class, making it easy
    to catch all SDK-related errors with a single except clause.

    Args:
        message: Human-readable error description.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        return self.message


class BackendError(AgenterError):
    """Error from the coding backend (e.g., API failure).

    Raised when communication with the LLM backend fails, including
    authentication errors, rate limits, and network issues.

    Args:
        message: Human-readable error description.
        backend: Name of the backend that failed (e.g., "anthropic-sdk", "claude-code").
        cause: The underlying exception, if any.
    """

    def __init__(
        self,
        message: str,
        *,
        backend: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.backend = backend
        self.cause = cause


class ValidationError(AgenterError):
    """Error during code validation.

    Raised when validators fail to validate the generated code. Contains
    details about which validators failed and specific error messages.

    Args:
        message: Human-readable error description.
        validator: Name of the validator that failed.
        errors: List of specific validation error messages.
    """

    def __init__(
        self,
        message: str,
        *,
        validator: str | None = None,
        errors: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.validator = validator
        self.errors = errors or []


class BudgetExceededError(AgenterError):
    """Budget limit exceeded during execution.

    Raised when any configured budget limit is reached (iterations, tokens,
    cost, or time).

    Args:
        message: Human-readable error description.
        limit_type: Type of limit exceeded ("iterations", "tokens", "cost", "time").
        limit_value: The configured limit value.
        actual_value: The actual value that exceeded the limit.
    """

    def __init__(
        self,
        message: str,
        *,
        limit_type: str,
        limit_value: float | int,
        actual_value: float | int,
    ) -> None:
        super().__init__(message)
        self.limit_type = limit_type
        self.limit_value = limit_value
        self.actual_value = actual_value


class ToolExecutionError(AgenterError):
    """Error during tool execution.

    Raised when a tool fails to execute properly. This includes both
    built-in file tools and custom user-defined tools.

    Args:
        message: Human-readable error description.
        tool_name: Name of the tool that failed.
        inputs: The inputs that were passed to the tool.
        cause: The underlying exception, if any.
    """

    def __init__(
        self,
        message: str,
        *,
        tool_name: str,
        inputs: dict | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.tool_name = tool_name
        self.inputs = inputs
        self.cause = cause


class PathSecurityError(AgenterError):
    """Security violation in path operations.

    Raised when a path operation would violate security constraints,
    such as attempting to access files outside the working directory
    or writing to disallowed paths.

    Args:
        message: Human-readable error description.
        path: The problematic path.
        cwd: The configured working directory.
        reason: Specific reason for the security violation.
    """

    def __init__(
        self,
        message: str,
        *,
        path: str | Path,
        cwd: str | Path | None = None,
        reason: str | None = None,
    ) -> None:
        super().__init__(message)
        self.path = str(path)
        self.cwd = str(cwd) if cwd else None
        self.reason = reason


class ConfigurationError(AgenterError):
    """Invalid SDK configuration.

    Raised when the SDK is configured incorrectly, such as missing
    required environment variables or invalid parameter combinations.

    Args:
        message: Human-readable error description.
        parameter: The configuration parameter that is invalid.
        value: The invalid value, if applicable.
    """

    def __init__(
        self,
        message: str,
        *,
        parameter: str | None = None,
        value: str | None = None,
    ) -> None:
        super().__init__(message)
        self.parameter = parameter
        self.value = value
