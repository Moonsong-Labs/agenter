"""Claude backend using Anthropic SDK with tool use.

This module provides the AnthropicSDKBackend class for executing coding tasks
using Claude models via the Anthropic API or AWS Bedrock.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import anthropic
import structlog

from ...config import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_MODEL_ANTHROPIC,
    DEFAULT_MODEL_BEDROCK,
    is_bedrock,
)
from ...data_models import (
    BackendError,
    BackendMessage,
    ContentModifiedFiles,
    PromptMessage,
    TextMessage,
    ToolCallMessage,
    ToolError,
    ToolErrorCode,
    ToolResult,
    Usage,
)
from ...file_system import PathResolver
from ...pricing import calculate_cost_usd
from ..base import BaseBackend
from ..output_parser import parse_structured_output
from ..prompts import DEFAULT_CODING_PROMPT as SYSTEM_PROMPT_TEMPLATE
from ..refusal import (
    REFUSAL_INSTRUCTIONS,
    REFUSAL_TOOL_DESCRIPTION,
    REFUSAL_TOOL_NAME,
    REFUSAL_TOOL_SCHEMA,
    parse_refusal_from_tool_call,
)
from .anthropic_tools import ANTHROPIC_TEXT_EDITOR, AnthropicTextEditor
from .client import AnthropicClient, BedrockClient, convert_tools_to_bedrock_format
from .constants import (
    ANTHROPIC_TEXT_EDITOR_TOOL,
    BEDROCK_TEXT_KEY,
    BEDROCK_TOOL_USE_KEY,
    BLOCK_TYPE_TEXT,
    BLOCK_TYPE_TOOL_USE,
    ROLE_ASSISTANT,
    ROLE_USER,
    STOP_REASON_END_TURN,
    STOP_REASON_MAX_TOKENS,
    TOOL_RESULT_ERROR_KEY,
    TOOL_RESULT_TYPE,
)
from .file_tools import FILE_TOOLS, FileTools

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pydantic import BaseModel

    from ...tools import Tool

logger = structlog.get_logger(__name__)

__all__ = ["AnthropicSDKBackend"]

# Tool name for Bedrock structured output
STRUCTURED_RESPONSE_TOOL = "structured_response"


class AnthropicSDKBackend(BaseBackend):
    """Coding backend using Claude models via Anthropic API or AWS Bedrock.

    Uses Anthropic SDK for standard API, boto3 for Bedrock.

    Args:
        model: Model identifier (Anthropic or Bedrock format).
        extra_tools: Additional custom tools (file tools are always included).
        use_anthropic_tools: Use Anthropic's built-in text_editor tool
            instead of custom file tools.
        sandbox: Enable sandboxed execution (default True). When True,
            enforces allowed_write_paths restrictions via PathResolver.
            When False, allows writes anywhere within cwd.

    Example:
        backend = AnthropicSDKBackend(model="claude-sonnet-4-20250514")
        await backend.connect("/path/to/project")

        async for message in backend.execute("Create a hello.py file"):
            print(message)
    """

    def __init__(
        self,
        model: str | None = None,
        extra_tools: list[Tool] | None = None,
        use_anthropic_tools: bool = False,
        sandbox: bool = True,
    ) -> None:
        use_bedrock = is_bedrock()
        default_model = DEFAULT_MODEL_BEDROCK if use_bedrock else DEFAULT_MODEL_ANTHROPIC
        self.model = model or default_model
        self._extra_tools = {t.name: t for t in (extra_tools or [])}
        self._use_bedrock = use_bedrock
        self._sandbox = sandbox

        # Force custom tools for Bedrock (built-in text editor not supported)
        if self._use_bedrock and use_anthropic_tools:
            logger.warning("use_anthropic_tools=True is not supported with Bedrock. Falling back to custom file tools.")
            self._use_anthropic_tools = False
        else:
            self._use_anthropic_tools = use_anthropic_tools

        # Clients (lazy initialized)
        self._anthropic_client = AnthropicClient()
        self._bedrock_client = BedrockClient()

        # Initialize common state (tokens, structured output, refusal)
        self._init_state()

        # State (set on connect)
        self._path_resolver: PathResolver | None = None
        self._file_tools: FileTools | None = None
        self._anthropic_text_editor: AnthropicTextEditor | None = None

    @property
    def cwd(self) -> Path | None:
        """The current working directory, if connected."""
        return self._path_resolver.cwd if self._path_resolver else None

    def _build_system_prompt(self) -> str:
        """Build the full system prompt with refusal instructions."""
        assert self._path_resolver is not None
        return self._build_system_prompt_from_template(
            cwd=self._path_resolver.cwd,
            template=SYSTEM_PROMPT_TEMPLATE,
            refusal_instructions=REFUSAL_INSTRUCTIONS,
            custom_prompt=self._custom_system_prompt,
        )

    def _handle_max_tokens(self) -> TextMessage:
        """Log warning and return truncation message for max_tokens limit."""
        logger.warning("Response truncated: hit max_tokens limit (%d)", DEFAULT_MAX_OUTPUT_TOKENS)
        return TextMessage(content=f"[Response truncated at {DEFAULT_MAX_OUTPUT_TOKENS} tokens.]", tokens=0)

    def _get_all_tools(self) -> list[dict]:
        """Get all tools (file + extra + refusal) in Anthropic format."""
        if self._use_anthropic_tools:
            tools: list[dict] = [ANTHROPIC_TEXT_EDITOR]
        else:
            tools = list(FILE_TOOLS)

        # Add refusal tool (shared across all backends)
        tools.append(
            {
                "name": REFUSAL_TOOL_NAME,
                "description": REFUSAL_TOOL_DESCRIPTION,
                "input_schema": REFUSAL_TOOL_SCHEMA,
            }
        )

        # Add extra custom tools
        for t in self._extra_tools.values():
            tools.append(
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
            )
        return tools

    async def connect(
        self,
        cwd: str,
        allowed_write_paths: list[str] | None = None,
        resume_session_id: str | None = None,  # Not supported, included for protocol
        output_type: type[BaseModel] | None = None,
        system_prompt: str | None = None,
    ) -> None:
        """Initialize with working directory and optional write restrictions.

        Args:
            cwd: Working directory for file operations.
            allowed_write_paths: Optional glob patterns restricting writes.
            resume_session_id: Not supported by AnthropicSDKBackend (ignored).
                Use ClaudeCodeBackend for session resume capability.
            output_type: Optional Pydantic model for structured output.
                Uses Anthropic's native structured output beta.
            system_prompt: Custom system prompt. If None, uses default template.
        """
        self._custom_system_prompt = system_prompt
        # Note: resume_session_id is ignored - AnthropicSDKBackend doesn't support session resume
        if resume_session_id:
            logger.warning(
                "resume_session_id is not supported by AnthropicSDKBackend. "
                "Use ClaudeCodeBackend for session resume capability."
            )

        # When sandbox=False, allow writes anywhere within cwd
        effective_write_paths = allowed_write_paths
        if not self._sandbox:
            logger.info(
                "sandbox_disabled",
                message="sandbox=False: allowing writes anywhere within cwd. "
                "Note: AnthropicSDKBackend always enforces cwd containment for safety.",
            )
            effective_write_paths = None  # No restrictions within cwd

        self._path_resolver = PathResolver(
            Path(cwd).resolve(),
            effective_write_paths,
        )

        # Initialize file tools or anthropic text editor
        if self._use_anthropic_tools:
            self._anthropic_text_editor = AnthropicTextEditor(self._path_resolver)
        else:
            self._file_tools = FileTools(self._path_resolver)

        # Reset common state and set output_type
        self._reset_state()
        self._output_type = output_type
        if output_type:
            logger.debug("structured_output_enabled", output_type=output_type.__name__)

        logger.debug(
            "backend_connected",
            cwd=str(self._path_resolver.cwd),
            model=self.model,
            use_anthropic_tools=self._use_anthropic_tools,
            structured_output=output_type.__name__ if output_type else None,
        )

    async def execute(self, prompt: str) -> AsyncIterator[BackendMessage]:
        """Execute prompt with tool use loop.

        Args:
            prompt: The user prompt to execute.

        Yields:
            BackendMessage for each significant step.

        Raises:
            BackendError: If backend is not connected.
        """
        if self._path_resolver is None:
            raise BackendError(
                "Backend not connected. Call connect() first.",
                backend="anthropic-sdk",
            )

        if self._use_bedrock:
            async for msg in self._execute_bedrock(prompt):
                yield msg
        else:
            async for msg in self._execute_anthropic(prompt):
                yield msg

    async def _execute_anthropic(self, prompt: str) -> AsyncIterator[BackendMessage]:
        """Execute using Anthropic API."""
        system_prompt = self._build_system_prompt()
        messages: list[dict] = [{"role": ROLE_USER, "content": prompt}]

        yield PromptMessage(user_prompt=prompt, system_prompt=system_prompt)

        tools = self._get_all_tools()

        # Get output schema if structured output is configured
        output_schema = None
        if self._output_type is not None:
            output_schema = self._output_type.model_json_schema()

        # Track last text response for structured output parsing
        last_text_content: str = ""

        while True:
            try:
                response = await self._anthropic_client.create_message(
                    model=self.model,
                    system=system_prompt,
                    messages=messages,
                    tools=tools,
                    output_schema=output_schema,
                )
            except anthropic.NotFoundError as e:
                raise BackendError(
                    f"Invalid model '{self.model}' for anthropic-sdk backend",
                    backend="anthropic-sdk",
                    cause=e,
                ) from e
            except anthropic.BadRequestError as e:
                if "model" in str(e).lower():
                    raise BackendError(
                        f"Invalid model '{self.model}' for anthropic-sdk backend",
                        backend="anthropic-sdk",
                        cause=e,
                    ) from e
                raise

            self._input_tokens += response.usage.input_tokens
            self._output_tokens += response.usage.output_tokens
            logger.debug(
                "api_response_received",
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                stop_reason=response.stop_reason,
            )

            assistant_content: list = []
            tool_uses: list = []

            for block in response.content:
                if block.type == BLOCK_TYPE_TEXT:
                    yield TextMessage(content=block.text, tokens=response.usage.output_tokens)
                    assistant_content.append(block)
                    last_text_content = block.text  # Track for structured output
                elif block.type == BLOCK_TYPE_TOOL_USE:
                    # Check for refusal tool call (using shared helper)
                    refusal = parse_refusal_from_tool_call(block.name, block.input)
                    if refusal is not None:
                        self._capture_refusal(refusal.reason, refusal.category)
                        yield refusal
                        logger.info("refusal_captured", reason=refusal.reason, category=refusal.category)
                        assistant_content.append(block)
                        # Don't add to tool_uses - refusal is a signal, not a real tool
                        continue

                    yield ToolCallMessage(tool_name=block.name, args=block.input)
                    assistant_content.append(block)
                    tool_uses.append(block)

            if response.stop_reason == STOP_REASON_MAX_TOKENS:
                yield self._handle_max_tokens()
                break

            if not tool_uses:
                break

            messages.append({"role": ROLE_ASSISTANT, "content": assistant_content})

            tool_results = []
            for tool_use in tool_uses:
                result = await self._execute_tool(tool_use.name, tool_use.input)
                yield ToolResult(
                    tool_name=tool_use.name,
                    output=result.output,
                    success=result.success,
                )
                tool_result = {
                    "type": TOOL_RESULT_TYPE,
                    "tool_use_id": tool_use.id,
                    "content": result.output,
                }
                if not result.success:
                    tool_result[TOOL_RESULT_ERROR_KEY] = True
                tool_results.append(tool_result)

            messages.append({"role": ROLE_USER, "content": tool_results})

            if response.stop_reason == STOP_REASON_END_TURN:
                break

        # Parse structured output from last text response
        self._structured_output = parse_structured_output(last_text_content, self._output_type)

    async def _execute_bedrock(self, prompt: str) -> AsyncIterator[BackendMessage]:
        """Execute using Bedrock Converse API."""
        system_prompt = self._build_system_prompt()
        messages: list[dict] = [{"role": ROLE_USER, "content": [{BEDROCK_TEXT_KEY: prompt}]}]

        yield PromptMessage(user_prompt=prompt, system_prompt=system_prompt)

        tools = convert_tools_to_bedrock_format(self._get_all_tools())

        # Add structured_response tool if output_type is configured
        # Bedrock doesn't support native structured output, so we use tool calling
        if self._output_type is not None:
            structured_tool = {
                "toolSpec": {
                    "name": STRUCTURED_RESPONSE_TOOL,
                    "description": "Submit the final structured response. Call this tool with your completed output.",
                    "inputSchema": {"json": self._output_type.model_json_schema()},
                }
            }
            tools.append(structured_tool)

        while True:
            try:
                response = await self._bedrock_client.converse(
                    model_id=self.model,
                    system=[{"text": system_prompt}],
                    messages=messages,
                    tool_config={"tools": tools},
                )
            except Exception as e:
                # Bedrock uses botocore.exceptions.ClientError
                # Check error code for model-related failures
                error_code = ""
                if hasattr(e, "response") and isinstance(e.response, dict):
                    error_code = e.response.get("Error", {}).get("Code", "")
                if error_code in ("ValidationException", "ResourceNotFoundException"):
                    raise BackendError(
                        f"Invalid model '{self.model}' for Bedrock backend",
                        backend="bedrock",
                        cause=e,
                    ) from e
                raise

            usage = response.get("usage", {})
            self._input_tokens += usage.get("inputTokens", 0)
            self._output_tokens += usage.get("outputTokens", 0)

            output = response.get("output", {})
            message = output.get("message", {})
            content = message.get("content", [])

            assistant_content: list = []
            tool_uses: list = []

            for block in content:
                if BEDROCK_TEXT_KEY in block:
                    yield TextMessage(
                        content=block[BEDROCK_TEXT_KEY],
                        tokens=usage.get("outputTokens", 0),
                    )
                    assistant_content.append(block)
                elif BEDROCK_TOOL_USE_KEY in block:
                    tool_use = block[BEDROCK_TOOL_USE_KEY]
                    tool_name = tool_use["name"]
                    tool_input = tool_use.get("input", {})

                    # Check for refusal tool call (using shared helper)
                    refusal = parse_refusal_from_tool_call(tool_name, tool_input)
                    if refusal is not None:
                        self._capture_refusal(refusal.reason, refusal.category)
                        yield refusal
                        logger.info("refusal_captured", reason=refusal.reason, category=refusal.category)
                        assistant_content.append(block)
                        # Don't add to tool_uses - refusal is a signal, not a real tool
                        continue

                    yield ToolCallMessage(
                        tool_name=tool_name,
                        args=tool_input,
                    )
                    assistant_content.append(block)
                    tool_uses.append(tool_use)

            if response.get("stopReason") == STOP_REASON_MAX_TOKENS:
                yield self._handle_max_tokens()
                break

            if not tool_uses:
                break

            messages.append({"role": ROLE_ASSISTANT, "content": assistant_content})

            tool_results = []
            for tool_use in tool_uses:
                tool_name = tool_use["name"]
                tool_input = tool_use.get("input", {})

                # Handle structured_response tool - capture output instead of executing
                if tool_name == STRUCTURED_RESPONSE_TOOL and self._output_type is not None:
                    try:
                        self._structured_output = self._output_type.model_validate(tool_input)
                        logger.debug("structured_output_captured", type=type(self._structured_output).__name__)
                        result = ToolResult(output="Structured output recorded.", success=True)
                    except (ValueError, TypeError) as e:
                        # Pydantic ValidationError inherits from ValueError
                        logger.warning("structured_output_validation_failed", error=str(e))
                        result = ToolResult(
                            output=f"Validation error: {e}",
                            success=False,
                            error=ToolError(code=ToolErrorCode.INVALID_INPUT, message=str(e)),
                        )
                else:
                    result = await self._execute_tool(tool_name, tool_input)

                yield ToolResult(
                    tool_name=tool_name,
                    output=result.output,
                    success=result.success,
                )
                tool_results.append(
                    {
                        "toolResult": {
                            "toolUseId": tool_use["toolUseId"],
                            "content": [{BEDROCK_TEXT_KEY: result.output}],
                            "status": "success" if result.success else "error",
                        }
                    }
                )

            messages.append({"role": ROLE_USER, "content": tool_results})

            if response.get("stopReason") == STOP_REASON_END_TURN:
                break

        # Structured output is captured via structured_response tool call above

    async def _execute_tool(self, name: str, inputs: dict) -> ToolResult:
        """Execute a tool and return result."""

        # Anthropic built-in text editor
        if self._use_anthropic_tools and name == ANTHROPIC_TEXT_EDITOR_TOOL:
            if self._anthropic_text_editor:
                return await self._anthropic_text_editor.execute(inputs)
            return ToolResult(
                output="Error: Text editor not initialized",
                success=False,
                error=ToolError(code=ToolErrorCode.EXECUTION_ERROR, message="Text editor not initialized"),
            )

        # Custom tools
        if name in self._extra_tools:
            try:
                return await self._extra_tools[name].execute(inputs)
            except Exception as e:
                logger.error("custom_tool_error", tool=name, error=str(e))
                return ToolResult(
                    output=f"Error: {e}",
                    success=False,
                    error=ToolError(code=ToolErrorCode.EXECUTION_ERROR, message=str(e)),
                )

        # Built-in file tools
        if self._file_tools:
            return await self._file_tools.execute(name, inputs)

        return ToolResult(
            output=f"Unknown tool: {name}",
            success=False,
            error=ToolError(code=ToolErrorCode.UNKNOWN_TOOL, message=name),
        )

    def modified_files(self) -> ContentModifiedFiles:
        """Return files modified during execution."""
        if self._use_anthropic_tools and self._anthropic_text_editor:
            files = self._anthropic_text_editor.modified_files()
        elif self._file_tools:
            files = self._file_tools.modified_files()
        else:
            files = {}
        return ContentModifiedFiles(files=files)

    def usage(self) -> Usage:
        """Return token usage and cost across all executions."""
        return Usage(
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
            cost_usd=calculate_cost_usd(self.model, self._input_tokens, self._output_tokens),
            model=self.model,
            provider="bedrock" if self._use_bedrock else "anthropic",
        )

    # structured_output() is inherited from BaseBackend

    async def disconnect(self) -> None:
        """Clean up resources and reset connection state.

        After disconnect(), the backend is in the same state as a newly
        constructed instance. Call connect() again before using execute().

        Resets internal state. No external resources to close since
        Anthropic client is stateless HTTP.
        """
        # Reset connection state
        self._path_resolver = None
        self._file_tools = None
        self._anthropic_text_editor = None

        # Reset common state (tokens, structured output, refusal)
        self._reset_state()
