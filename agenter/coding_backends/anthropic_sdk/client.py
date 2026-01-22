"""API client logic for Anthropic and AWS Bedrock.

This module provides client management and API call handling for both
the direct Anthropic API and AWS Bedrock.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, cast

import anthropic
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ...config import DEFAULT_AWS_REGION, DEFAULT_MAX_OUTPUT_TOKENS

if TYPE_CHECKING:
    from collections.abc import Iterable

    from anthropic.types import MessageParam, ToolParam
    from botocore.client import BaseClient
    from tenacity import RetryCallState

logger = structlog.get_logger(__name__)

# Retry configuration
ANTHROPIC_MAX_RETRIES = 5
ANTHROPIC_RETRY_MIN_SECONDS = 2
ANTHROPIC_RETRY_MAX_SECONDS = 30

BEDROCK_MAX_RETRIES = 8
BEDROCK_RETRY_MIN_SECONDS = 1
BEDROCK_RETRY_MAX_SECONDS = 60
BEDROCK_READ_TIMEOUT_SECONDS = 300

# Retry settings for Anthropic API calls
ANTHROPIC_RETRY_STOP = stop_after_attempt(ANTHROPIC_MAX_RETRIES)
ANTHROPIC_RETRY_WAIT = wait_exponential(multiplier=1, min=ANTHROPIC_RETRY_MIN_SECONDS, max=ANTHROPIC_RETRY_MAX_SECONDS)
ANTHROPIC_RETRY_EXCEPTIONS = (
    anthropic.RateLimitError,
    anthropic.APIConnectionError,
    anthropic.InternalServerError,
)


class AnthropicClient:
    """Wrapper for the Anthropic async client.

    Provides lazy initialization of the client.
    """

    def __init__(self) -> None:
        self._client: anthropic.AsyncAnthropic | None = None

    def get(self) -> anthropic.AsyncAnthropic:
        """Get or create the Anthropic client."""
        if self._client is None:
            self._client = anthropic.AsyncAnthropic()
        return self._client

    @retry(
        stop=ANTHROPIC_RETRY_STOP,
        wait=ANTHROPIC_RETRY_WAIT,
        retry=retry_if_exception_type(ANTHROPIC_RETRY_EXCEPTIONS),
        reraise=True,
    )
    async def create_message(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict],
        tools: list[dict],
        output_schema: dict | None = None,
    ) -> anthropic.types.Message:
        """Create a message using the Anthropic API.

        Includes automatic retry with exponential backoff for:
        - Rate limit errors (429)
        - Connection errors
        - Internal server errors (500)

        Args:
            model: Model identifier.
            system: System prompt.
            messages: Conversation messages.
            tools: Available tools.
            output_schema: Optional JSON schema for structured output.
                When provided, uses Anthropic's structured output beta.

        Returns:
            The API response message.
        """
        client = self.get()

        if output_schema:
            # Use beta API for structured output
            # Cast to Any to handle beta API type differences (BetaMessageParam vs MessageParam)
            return cast(
                "anthropic.types.Message",
                await client.beta.messages.create(
                    model=model,
                    max_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
                    system=system,
                    tools=cast("Any", tools),
                    messages=cast("Any", messages),
                    betas=["structured-outputs-2025-11-13"],
                    output_format=cast("Any", {"type": "json_schema", "schema": output_schema}),
                ),
            )

        return await client.messages.create(
            model=model,
            max_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
            system=system,
            tools=cast("Iterable[ToolParam]", tools),
            messages=cast("Iterable[MessageParam]", messages),
        )


def _is_bedrock_throttling(retry_state: RetryCallState) -> bool:
    """Check if exception is a Bedrock throttling error."""
    # Import here to avoid import-time dependency on botocore
    try:
        from botocore.exceptions import ClientError
    except ImportError:
        return False

    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if exc and isinstance(exc, ClientError):
        return exc.response.get("Error", {}).get("Code") == "ThrottlingException"
    return False


# Bedrock-specific retry settings (throttling only)
BEDROCK_RETRY_STOP = stop_after_attempt(BEDROCK_MAX_RETRIES)
BEDROCK_RETRY_WAIT = wait_exponential(multiplier=1, min=BEDROCK_RETRY_MIN_SECONDS, max=BEDROCK_RETRY_MAX_SECONDS)


class BedrockClient:
    """Wrapper for AWS Bedrock converse API.

    Provides lazy initialization and automatic retry with exponential backoff.
    """

    def __init__(self) -> None:
        self._client: BaseClient | None = None

    def get(self) -> BaseClient:
        """Get or create the Bedrock client."""
        if self._client is None:
            import os

            import boto3
            from botocore.config import Config

            self._client = boto3.client(
                "bedrock-runtime",
                region_name=os.environ.get("AWS_REGION", DEFAULT_AWS_REGION),
                config=Config(read_timeout=BEDROCK_READ_TIMEOUT_SECONDS),
            )
        return self._client

    @retry(
        stop=BEDROCK_RETRY_STOP,
        wait=BEDROCK_RETRY_WAIT,
        retry=_is_bedrock_throttling,
        reraise=True,
    )
    async def converse(
        self,
        *,
        model_id: str,
        system: list[dict],
        messages: list[dict],
        tool_config: dict,
    ) -> dict[str, Any]:
        """Call Bedrock converse API with automatic retry on throttling.

        Includes automatic retry with exponential backoff for throttling errors.

        Args:
            model_id: Bedrock model identifier.
            system: System prompt blocks.
            messages: Conversation messages.
            tool_config: Tool configuration.

        Returns:
            The API response dictionary.

        Raises:
            ClientError: If all retries are exhausted or non-throttling error.
        """
        client = self.get()
        return await asyncio.to_thread(
            client.converse,
            modelId=model_id,
            system=system,
            messages=messages,
            toolConfig=tool_config,
            inferenceConfig={"maxTokens": DEFAULT_MAX_OUTPUT_TOKENS},
        )


def convert_tools_to_bedrock_format(tools: list[dict]) -> list[dict]:
    """Convert Anthropic tool format to Bedrock format.

    Args:
        tools: Tools in Anthropic format.

    Returns:
        Tools in Bedrock format.
    """
    bedrock_tools = []
    for tool in tools:
        # Skip special tool types (like text_editor_20250728)
        if tool.get("type"):
            continue
        bedrock_tools.append(
            {
                "toolSpec": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "inputSchema": {"json": tool["input_schema"]},
                }
            }
        )
    return bedrock_tools
