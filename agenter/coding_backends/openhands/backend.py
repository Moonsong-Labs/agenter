"""OpenHands backend using openhands-sdk.

This backend wraps openhands-sdk for model-agnostic agent execution via litellm.
Supports any model: Anthropic, OpenAI, Bedrock, Vertex, etc.

WARNING: SECURITY LIMITATIONS
=============================
This backend does NOT enforce path restrictions:
- Files can be read/written ANYWHERE on the filesystem
- Uses LocalWorkspace with direct filesystem access
- allowed_write_paths is NOT enforced

For strict path sandboxing, use AnthropicSDKBackend instead.

To use this backend, you MUST set sandbox=False to acknowledge these risks.

Requires the openhands optional dependency:
    pip install agenter[openhands]

Supports any model via litellm format:
    - anthropic/claude-sonnet-4-5-20250929
    - openai/gpt-4
    - bedrock/anthropic.claude-v2
    - vertex_ai/gemini-pro
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from ...data_models import (
    BackendError,
    BackendMessage,
    ConfigurationError,
    PathsModifiedFiles,
    PromptMessage,
    TextMessage,
    ToolCallMessage,
    ToolResult,
    Usage,
)
from ...pricing import calculate_cost_usd
from ..base import BaseBackend
from ..output_parser import parse_structured_output
from ..prompts import DEFAULT_CODING_PROMPT
from ..refusal import (
    REFUSAL_INSTRUCTIONS,
    parse_refusal_from_tool_call,
)
from .constants import (
    DEFAULT_MODEL_OPENHANDS,
    FILE_MODIFICATION_TOOLS,
    PATH_INPUT_KEYS,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from pydantic import BaseModel

    from ...tools import Tool

logger = structlog.get_logger(__name__)

# Module-level observation class for custom tools (required by OpenHands SDK serialization)
# OpenHands SDK cannot serialize local classes defined inside functions
_CustomToolObservation: type | None = None


def _get_custom_tool_observation() -> type:
    """Get or create the CustomToolObservation class.

    Lazily creates the class to avoid import errors when openhands is not installed.
    The class is created with module-level __qualname__ so OpenHands SDK can serialize it.
    """
    global _CustomToolObservation
    if _CustomToolObservation is not None:
        return _CustomToolObservation

    try:
        from openhands.sdk import Observation, TextContent
    except ImportError as e:
        raise BackendError("openhands-sdk not installed") from e

    # Create class dynamically with proper __qualname__ (no <locals>)
    # This makes OpenHands SDK treat it as a module-level class
    def to_llm_content_method(self: Any) -> list:
        return [TextContent(text=self.output)]

    CustomToolObservation = type(
        "CustomToolObservation",
        (Observation,),
        {
            "__module__": __name__,
            "__qualname__": "CustomToolObservation",
            "__doc__": "Observation for custom tool execution results.",
            "__annotations__": {"output": str, "success": bool},
            "output": "",
            "success": True,
            "to_llm_content": property(to_llm_content_method),
        },
    )

    _CustomToolObservation = CustomToolObservation
    # Also register at module level so it can be imported
    globals()["CustomToolObservation"] = CustomToolObservation
    return _CustomToolObservation


class OpenHandsBackend(BaseBackend):
    """Backend using openhands-sdk (OpenHands as library).

    WARNING: This backend does NOT enforce path restrictions. Files can be
    read/written anywhere on the filesystem. Set sandbox=False to use.

    Uses OpenHands SDK which provides:
    - Model-agnostic execution via litellm
    - Built-in file tools (str_replace_editor, terminal, etc.)
    - LocalWorkspace for direct filesystem access

    Example:
        # Basic usage (sandbox=False required - no sandboxing support)
        backend = OpenHandsBackend(sandbox=False)
        await backend.connect("/path/to/project")
        async for message in backend.execute("Fix the bug"):
            print(message)

    For strict path sandboxing, use AnthropicSDKBackend instead.
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        extra_tools: list[Tool] | None = None,
        sandbox: bool = True,
    ) -> None:
        """Initialize the backend.

        Args:
            model: Model identifier in litellm format. Examples:
                - "anthropic/claude-sonnet-4-5-20250929" (default)
                - "openai/gpt-4"
                - "bedrock/anthropic.claude-v2"
                - "vertex_ai/gemini-pro"
            extra_tools: Custom tools to add. Note: OpenHands uses its own
                tool format; custom tools are converted automatically.
            sandbox: Must be False (OpenHands does NOT support sandboxing).
                Files can be read/written anywhere on the filesystem.
                For strict sandboxing, use AnthropicSDKBackend instead.

        Raises:
            ConfigurationError: If sandbox is True (not supported).
        """
        if sandbox:
            raise ConfigurationError(
                "OpenHandsBackend does NOT support sandboxing. "
                "Files can be read/written anywhere on the filesystem. "
                "Set sandbox=False to acknowledge this risk, "
                "or use AnthropicSDKBackend for strict sandboxing.",
                parameter="sandbox",
                value="True",
            )

        self.model = model or DEFAULT_MODEL_OPENHANDS
        self._extra_tools = extra_tools or []

        # Initialize common state (tokens, structured output, refusal)
        self._init_state()

        # Connection state (set on connect)
        self._cwd: Path | None = None
        self._files_modified: list[str] = []
        self._last_text_content: str = ""

        # SDK objects (lazy initialized)
        self._llm: Any = None
        self._agent: Any = None
        self._conversation: Any = None

    @property
    def cwd(self) -> Path | None:
        """The current working directory, if connected."""
        return self._cwd

    def _build_system_prompt(self) -> str:
        """Build the full system prompt with refusal instructions."""
        assert self._cwd is not None
        return self._build_system_prompt_from_template(
            cwd=self._cwd,
            template=DEFAULT_CODING_PROMPT,
            refusal_instructions=REFUSAL_INSTRUCTIONS,
            custom_prompt=self._custom_system_prompt,
        )

    async def connect(
        self,
        cwd: str,
        allowed_write_paths: list[str] | None = None,
        resume_session_id: str | None = None,
        output_type: type[BaseModel] | None = None,
        system_prompt: str | None = None,
    ) -> None:
        """Initialize with working directory and optional configurations.

        Args:
            cwd: Working directory for file operations.
            allowed_write_paths: Optional glob patterns restricting writes.
                WARNING: These are NOT enforced by OpenHands SDK.
                The agent can still write anywhere.
            resume_session_id: Not supported by OpenHandsBackend (ignored).
            output_type: Optional Pydantic model for structured output.
                Parsed from final response text.
            system_prompt: Custom system prompt. If None, uses default template.
        """
        self._custom_system_prompt = system_prompt
        if resume_session_id:
            logger.warning(
                "resume_session_id_not_supported",
                backend="openhands",
                session_id=resume_session_id,
            )
        self._cwd = Path(cwd).resolve()
        self._files_modified = []
        self._last_text_content = ""

        # Reset common state (tokens, structured output, refusal)
        self._reset_state()
        self._output_type = output_type

        if output_type:
            logger.debug("structured_output_enabled", output_type=output_type.__name__)

        # Log warning if allowed_write_paths is set (it won't be enforced)
        if allowed_write_paths:
            logger.warning(
                "allowed_write_paths is set but NOT enforced by OpenHandsBackend. "
                "The agent can still write files anywhere. "
                "Use AnthropicSDKBackend for strict path restrictions.",
            )

        logger.debug(
            "backend_connected",
            cwd=str(self._cwd),
            model=self.model,
        )

    async def execute(self, prompt: str) -> AsyncIterator[BackendMessage]:
        """Execute a prompt using openhands-sdk.

        Args:
            prompt: The user prompt to execute.

        Yields:
            BackendMessage objects for each significant step.

        Raises:
            BackendError: If SDK not installed or not connected.
        """
        import os

        try:
            from openhands.sdk import (  # type: ignore[import-not-found]  # noqa: I001
                Agent,
                Conversation,
                LLM,
                Tool,
                register_tool,
            )
            from openhands.tools.file_editor import FileEditorTool  # type: ignore[import-not-found]
            from openhands.tools.task_tracker import TaskTrackerTool  # type: ignore[import-not-found]
            from openhands.tools.terminal import TerminalTool  # type: ignore[import-not-found]
            from pydantic import SecretStr
        except ImportError as e:
            raise BackendError(
                "openhands-sdk is required for OpenHandsBackend. Install with: pip install agenter[openhands]",
                backend="openhands",
                cause=e,
            ) from e

        if self._cwd is None:
            raise BackendError(
                "Backend not connected. Call connect() first.",
                backend="openhands",
            )

        # Build system prompt
        system_prompt = self._build_system_prompt()

        # Yield PromptMessage for tracing
        yield PromptMessage(user_prompt=prompt, system_prompt=system_prompt)

        # Get API key from environment (OpenHands uses litellm which checks various env vars)
        api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")

        # Initialize SDK components
        self._llm = LLM(
            model=self.model,
            api_key=SecretStr(api_key) if api_key else None,
        )

        # Register built-in tools from openhands.tools
        tools: list[Any] = [
            Tool(name=FileEditorTool.name),
            Tool(name=TerminalTool.name),
            Tool(name=TaskTrackerTool.name),
        ]

        # Register and add extra tools
        for t in self._extra_tools:
            tool_def = self._convert_tool_to_openhands(t)
            if tool_def is not None:
                # Register the tool so it can be resolved by name
                register_tool(t.name, tool_def)
                tools.append(Tool(name=t.name))
                logger.debug("extra_tool_registered", tool_name=t.name)

        self._agent = Agent(llm=self._llm, tools=tools)

        # Collect events via callback (SDK uses synchronous callbacks)
        collected_events: list[Any] = []

        def on_event(event: Any) -> None:
            collected_events.append(event)

        # Create conversation with workspace as string path
        self._conversation = Conversation(
            agent=self._agent,
            callbacks=[on_event],
            workspace=str(self._cwd),
        )

        logger.debug("executing_with_openhands_sdk", cwd=str(self._cwd), model=self.model)

        # Run conversation synchronously (wrapped in executor for async compatibility)
        # The SDK's conversation.run() is synchronous
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._run_conversation, prompt)
        except Exception as e:
            # Handle SDK-specific errors gracefully
            error_msg = str(e)
            if "model" in error_msg.lower() and ("not found" in error_msg.lower() or "invalid" in error_msg.lower()):
                raise BackendError(
                    f"Invalid model '{self.model}' for OpenHands backend",
                    backend="openhands",
                    cause=e,
                ) from e
            raise

        # Convert collected events to BackendMessages
        for event in collected_events:
            for message in self._convert_event(event):
                yield message

        # Extract usage from LLM metrics
        self._extract_usage()

        # Parse structured output from last text response
        self._structured_output = parse_structured_output(self._last_text_content, self._output_type)

    def _run_conversation(self, prompt: str) -> None:
        """Run conversation synchronously (called from executor).

        The OpenHands SDK uses synchronous execution with callbacks.
        This method is called via run_in_executor for async compatibility.
        """
        assert self._conversation is not None
        self._conversation.send_message(prompt)
        self._conversation.run()

    def _convert_event(self, event: Any) -> list[BackendMessage]:
        """Convert OpenHands event to list of BackendMessages.

        Uses SDK event types from openhands.sdk.event:
        - ActionEvent: tool calls (has tool_name, action)
        - ObservationEvent: tool results (has tool_name, observation)
        - AssistantEvent: text responses (has extended_content)

        Args:
            event: Event from openhands-sdk.

        Returns:
            List of converted BackendMessages (may be empty).
        """
        # Import SDK event types for isinstance checks
        try:
            from openhands.sdk.event import (  # type: ignore[import-not-found]
                ActionEvent,
                MessageEvent,
                ObservationEvent,
            )
        except ImportError:
            # SDK not available, skip event conversion
            logger.warning("openhands.sdk.event not available, skipping event")
            return []

        results: list[BackendMessage] = []

        # MessageEvent: text responses (formerly AssistantEvent)
        if isinstance(event, MessageEvent):
            content = getattr(event, "content", None) or getattr(event, "message", None)
            if content:
                self._last_text_content = str(content)
                results.append(TextMessage(content=str(content)))

        # ActionEvent: tool calls
        elif isinstance(event, ActionEvent):
            tool_name = event.tool_name

            # Extract args from action object
            tool_args: dict[str, Any] = {}
            if event.action is not None:
                if hasattr(event.action, "model_dump"):
                    tool_args = event.action.model_dump()
                elif hasattr(event.action, "dict"):
                    tool_args = event.action.dict()

            # Check for refusal
            refusal = parse_refusal_from_tool_call(tool_name, tool_args)
            if refusal is not None:
                self._capture_refusal(refusal.reason, refusal.category)
                results.append(refusal)
                logger.info("refusal_captured", reason=refusal.reason, category=refusal.category)
                return results

            # Track file modifications
            if tool_name in FILE_MODIFICATION_TOOLS:
                for key in PATH_INPUT_KEYS:
                    path = tool_args.get(key)
                    if path:
                        abs_path = Path(path)
                        if abs_path.is_absolute() and self._cwd:
                            with contextlib.suppress(ValueError):
                                path = str(abs_path.relative_to(self._cwd))
                        if path not in self._files_modified:
                            self._files_modified.append(path)
                        break

            results.append(ToolCallMessage(tool_name=tool_name, args=tool_args))

        # ObservationEvent: tool results
        elif isinstance(event, ObservationEvent):
            tool_name = event.tool_name

            # Extract output from observation object
            output = ""
            if event.observation is not None:
                if hasattr(event.observation, "to_llm_content"):
                    content_list = event.observation.to_llm_content
                    # to_llm_content returns Sequence[TextContent | ImageContent]
                    output = " ".join(c.text for c in content_list if hasattr(c, "text"))
                else:
                    output = str(event.observation)

            results.append(
                ToolResult(
                    tool_name=tool_name,
                    output=output,
                    success=True,  # ObservationEvent doesn't have error flag
                )
            )

        return results

    def _convert_tool_to_openhands(self, tool: Tool) -> Any:
        """Convert a agenter Tool to an OpenHands tool factory.

        OpenHands uses a multi-class pattern:
        - Action: Pydantic model for inputs
        - Observation: Pydantic model for outputs (with to_llm_content)
        - ToolExecutor: Implements __call__(action) → observation
        - ToolDefinition: Ties them together (with create() factory method)

        Args:
            tool: A agenter Tool instance.

        Returns:
            A factory function that register_tool() accepts.
        """
        try:
            from openhands.sdk import (  # type: ignore[import-not-found]
                Action,
                ToolDefinition,
            )
            from openhands.sdk.tool import ToolExecutor  # type: ignore[import-not-found]
        except ImportError:
            logger.warning("openhands.sdk not available, cannot convert tool", tool_name=tool.name)
            return None

        from pydantic import Field, create_model

        # Capture tool for closures
        captured_tool = tool

        # 1. Create Action class from input_schema
        fields: dict[str, Any] = {}
        props = tool.input_schema.get("properties", {})
        required = set(tool.input_schema.get("required", []))

        for name, schema in props.items():
            # Map JSON schema types to Python types
            json_type = schema.get("type", "string")
            py_type: type = str
            if json_type == "integer":
                py_type = int
            elif json_type == "number":
                py_type = float
            elif json_type == "boolean":
                py_type = bool
            elif json_type == "array":
                py_type = list
            elif json_type == "object":
                py_type = dict

            description = schema.get("description", "")
            default = ... if name in required else None
            fields[name] = (py_type, Field(default=default, description=description))

        DynamicAction = create_model(
            f"{tool.name}Action",
            __base__=Action,
            **fields,
        )

        # 2. Get module-level Observation class (required for OpenHands SDK serialization)
        CustomToolObservation = _get_custom_tool_observation()

        # 3. Create Executor that calls tool.execute()
        class DynamicExecutor(ToolExecutor):  # type: ignore[misc]
            def __call__(self, action: Any, conversation: Any = None) -> Any:
                # Convert Action to dict
                inputs = action.model_dump()
                # Remove 'kind' field that's added by Pydantic but not part of tool args
                inputs.pop("kind", None)

                # Execute synchronously (wrap async)
                # OpenHands runs executors in a separate thread, so we use asyncio.run()
                try:
                    # Create a new event loop for this thread
                    result = asyncio.run(captured_tool.execute(inputs))
                except Exception as e:
                    logger.exception("tool_execution_failed", tool_name=captured_tool.name)
                    return CustomToolObservation(output=f"Error: {e}", success=False)

                return CustomToolObservation(output=result.output, success=result.success)

        # 4. Create ToolDefinition subclass with create() method
        # Use type() to create class with proper name (SDK derives tool name from class name)
        tool_class_name = f"{captured_tool.name.title().replace('_', '')}Tool"

        def create_method(cls: Any, *args: Any, **kwargs: Any) -> Sequence[ToolDefinition]:
            return [
                cls(
                    description=captured_tool.description,
                    action_type=DynamicAction,
                    observation_type=CustomToolObservation,
                    executor=DynamicExecutor(),
                )
            ]

        DynamicToolDefinition = type(
            tool_class_name,
            (ToolDefinition,),
            {"create": classmethod(create_method)},
        )

        return DynamicToolDefinition

    def _extract_usage(self) -> None:
        """Extract usage metrics from LLM."""
        if self._llm is None:
            return

        metrics = getattr(self._llm, "metrics", None)
        if metrics is None:
            return

        self._input_tokens = int(getattr(metrics, "input_tokens", 0) or 0)
        self._output_tokens = int(getattr(metrics, "output_tokens", 0) or 0)
        self._cost_usd = float(getattr(metrics, "accumulated_cost", 0.0) or 0.0)

    def modified_files(self) -> PathsModifiedFiles:
        """Return files modified during execution.

        Note: OpenHands tracks files internally. We return paths only;
        content must be read from disk if needed.
        """
        return PathsModifiedFiles(file_paths=list(self._files_modified))

    def usage(self) -> Usage:
        """Return token usage and cost across all executions."""
        cost = self._cost_usd or calculate_cost_usd(self.model, self._input_tokens, self._output_tokens)
        return Usage(
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
            cost_usd=cost,
            model=self.model,
            provider="openhands",
        )

    # structured_output() is inherited from BaseBackend

    async def disconnect(self) -> None:
        """Clean up resources and reset connection state.

        After disconnect(), the backend is in the same state as a newly
        constructed instance. Call connect() again before using execute().
        """
        # Clean up SDK objects
        self._llm = None
        self._agent = None
        self._conversation = None

        # Reset connection state
        self._cwd = None
        self._files_modified = []
        self._last_text_content = ""

        # Reset common state (tokens, structured output, refusal)
        self._reset_state()
