"""Retry prompt building."""

from __future__ import annotations


def build_retry_prompt(
    original_prompt: str,
    validation_errors: list[str],
    tool_failures: list[str],
) -> str:
    """Build a retry prompt with error context.

    Args:
        original_prompt: The original user prompt.
        validation_errors: Errors from validation (syntax, tests).
        tool_failures: Tool execution failures from the iteration.

    Returns:
        Combined prompt with error information for retry.
    """
    parts = [original_prompt]

    if validation_errors:
        error_text = "\n".join(validation_errors)
        parts.append(f"\n\nFix these validation errors:\n{error_text}")

    if tool_failures:
        failure_text = "\n".join(tool_failures)
        parts.append(f"\n\nPrevious tool failures to avoid:\n{failure_text}")

    return "".join(parts)
