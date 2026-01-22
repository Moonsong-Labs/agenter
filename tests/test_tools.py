"""Tests for the tool decorator and FunctionTool class."""

import pytest

from agenter import tool
from agenter.data_models import ToolErrorCode, ToolResult
from agenter.tools import FunctionTool, Tool, _types_to_schema


class TestToolDecorator:
    """Test the @tool decorator."""

    def test_creates_function_tool_with_type_hints_schema(self):
        """Decorator should convert Python type hints to JSON schema."""

        @tool("add", "Add two numbers", {"a": int, "b": int})
        async def add(args):
            return args["a"] + args["b"]

        assert isinstance(add, FunctionTool)
        assert add.name == "add"
        assert "properties" in add.input_schema
        assert add.input_schema["properties"]["a"]["type"] == "integer"
        assert add.input_schema["properties"]["b"]["type"] == "integer"

    def test_accepts_raw_json_schema(self):
        """Decorator should accept raw JSON schema dict."""
        schema = {"type": "object", "properties": {"query": {"type": "string"}}}

        @tool("search", "Search the web", schema)
        async def search(args):
            return f"Results for {args['query']}"

        assert search.input_schema == schema

    def test_none_or_empty_schema_becomes_empty_dict(self):
        """None or empty schema should result in empty dict."""

        @tool("ping", "Ping the server", None)
        async def ping(args):
            return "pong"

        @tool("version", "Get version", {})
        async def version(args):
            return "1.0.0"

        assert ping.input_schema == {}
        assert version.input_schema == {}


class TestFunctionTool:
    """Test FunctionTool execution."""

    @pytest.mark.asyncio
    async def test_executes_async_and_sync_functions(self):
        """FunctionTool should handle both async and sync functions."""

        async def async_func(args):
            return f"Hello, {args['name']}!"

        def sync_func(args):
            return args["a"] + args["b"]

        async_tool = FunctionTool(name="greet", description="Greet", input_schema={}, func=async_func)
        sync_tool = FunctionTool(name="add", description="Add", input_schema={}, func=sync_func)

        async_result = await async_tool.execute({"name": "World"})
        sync_result = await sync_tool.execute({"a": 2, "b": 3})

        assert async_result.success
        assert async_result.output == "Hello, World!"
        assert sync_result.success
        assert sync_result.output == "5"

    @pytest.mark.asyncio
    async def test_handles_various_return_types(self):
        """FunctionTool should normalize different return types to ToolResult."""

        # ToolResult passthrough
        async def returns_tool_result(args):
            return ToolResult(output="Custom", success=True)

        # Dict -> JSON
        async def returns_dict(args):
            return {"key": "value"}

        # String -> ToolResult with success=True
        async def returns_string(args):
            return "Plain string"

        for func, expected_output in [
            (returns_tool_result, "Custom"),
            (returns_dict, '{"key": "value"}'),
            (returns_string, "Plain string"),
        ]:
            tool_instance = FunctionTool(name="test", description="Test", input_schema={}, func=func)
            result = await tool_instance.execute({})
            assert result.success
            assert result.output == expected_output

    @pytest.mark.asyncio
    async def test_handles_exception_gracefully(self):
        """FunctionTool should catch exceptions and return error result."""

        async def failing(args):
            raise ValueError("Something went wrong")

        tool_instance = FunctionTool(name="failing", description="Failing", input_schema={}, func=failing)
        result = await tool_instance.execute({})

        assert result.success is False
        assert "Something went wrong" in result.output
        assert result.error is not None
        assert result.error.code == ToolErrorCode.EXECUTION_ERROR


class TestTypesToSchema:
    """Test the _types_to_schema helper function."""

    def test_converts_python_types_to_json_schema(self):
        """Python types should map to correct JSON schema types and mark all fields required."""
        schema = _types_to_schema({"name": str, "age": int, "score": float, "active": bool})

        assert schema["properties"]["name"]["type"] == "string"
        assert schema["properties"]["age"]["type"] == "integer"
        assert schema["properties"]["score"]["type"] == "number"
        assert schema["properties"]["active"]["type"] == "boolean"
        assert set(schema["required"]) == {"name", "age", "score", "active"}


class TestToolProtocol:
    """Test Tool protocol compliance."""

    @pytest.mark.asyncio
    async def test_custom_tool_class_implements_protocol(self):
        """Custom classes implementing Tool protocol should work."""
        from typing import ClassVar

        class CustomTool:
            name: ClassVar[str] = "custom"
            description: ClassVar[str] = "A custom tool"
            input_schema: ClassVar[dict] = {}

            async def execute(self, inputs: dict) -> ToolResult:
                return ToolResult(output="custom result", success=True)

        custom = CustomTool()
        assert isinstance(custom, Tool)
        result = await custom.execute({})
        assert result.output == "custom result"


class TestToolResultFromError:
    """Test ToolResult.from_error() factory method."""

    def test_creates_failed_result(self):
        result = ToolResult.from_error(ToolErrorCode.FILE_NOT_FOUND, "config.py")

        assert result.success is False
        assert result.output == "Error: config.py"
        assert result.error is not None
        assert result.error.code == ToolErrorCode.FILE_NOT_FOUND
        assert result.error.message == "config.py"

    def test_creates_result_with_all_error_codes(self):
        """All ToolErrorCode values should work with from_error()."""
        for code in ToolErrorCode:
            result = ToolResult.from_error(code, f"test message for {code.value}")
            assert result.success is False
            assert result.error.code == code
            assert f"test message for {code.value}" in result.error.message

    def test_includes_metadata(self):
        metadata = {"attempted_path": "/etc/passwd", "allowed_paths": ["/home/user/*"]}
        result = ToolResult.from_error(ToolErrorCode.PATH_SECURITY, "Access denied", metadata=metadata)

        assert result.metadata == metadata
        assert result.metadata["attempted_path"] == "/etc/passwd"

    def test_default_metadata_is_empty(self):
        result = ToolResult.from_error(ToolErrorCode.INVALID_INPUT, "Missing required field")

        assert result.metadata == {}

    def test_equivalent_to_manual_construction(self):
        """from_error() should produce same result as manual construction."""
        from_factory = ToolResult.from_error(ToolErrorCode.IO_ERROR, "Disk full")
        from agenter.data_models import ToolError

        manual = ToolResult(
            output="Error: Disk full",
            success=False,
            error=ToolError(code=ToolErrorCode.IO_ERROR, message="Disk full"),
        )

        assert from_factory.output == manual.output
        assert from_factory.success == manual.success
        assert from_factory.error.code == manual.error.code
        assert from_factory.error.message == manual.error.message


# Check for optional dependencies
try:
    from claude_agent_sdk import tool as sdk_tool  # noqa: F401

    HAS_CLAUDE_AGENT_SDK = True
except ImportError:
    HAS_CLAUDE_AGENT_SDK = False


class TestCustomToolsWithBackends:
    """Test custom tools work with all backends."""

    def test_anthropic_sdk_backend_accepts_custom_tools(self):
        """AnthropicSDKBackend should accept extra_tools."""
        from agenter.coding_backends.anthropic_sdk import AnthropicSDKBackend

        @tool("echo", "Echo input", {"text": str})
        async def echo(args):
            return f"Echo: {args['text']}"

        backend = AnthropicSDKBackend(model="claude-sonnet-4-20250514", extra_tools=[echo])
        # AnthropicSDKBackend stores tools as dict keyed by name
        assert "echo" in backend._extra_tools
        assert backend._extra_tools["echo"] is echo

    @pytest.mark.skipif(not HAS_CLAUDE_AGENT_SDK, reason="claude-agent-sdk not installed")
    def test_claude_code_backend_accepts_custom_tools(self):
        """ClaudeCodeBackend should accept extra_tools."""
        from agenter.coding_backends.claude_code import ClaudeCodeBackend

        @tool("search", "Search the web", {"query": str})
        async def search(args):
            return f"Results for {args['query']}"

        backend = ClaudeCodeBackend(sandbox=False, extra_tools=[search])
        assert backend._extra_tools == [search]

    def test_codex_backend_accepts_custom_tools(self):
        """CodexBackend should accept extra_tools."""
        from agenter.coding_backends.codex import CodexBackend

        @tool("test", "Test tool", {"x": str})
        async def test_tool(args):
            return args["x"]

        backend = CodexBackend(extra_tools=[test_tool])
        assert backend._extra_tools == [test_tool]

    def test_agent_passes_tools_to_codex_backend(self):
        """AutonomousCodingAgent should pass tools to CodexBackend."""
        from agenter import AutonomousCodingAgent

        @tool("custom", "Custom tool", {"arg": str})
        async def custom(args):
            return args["arg"]

        agent = AutonomousCodingAgent(backend="codex", tools=[custom])
        backend = agent._create_backend()

        assert backend._extra_tools == [custom]

    def test_agent_passes_tools_to_anthropic_sdk_backend(self):
        """AutonomousCodingAgent should pass tools to AnthropicSDKBackend."""
        from agenter import AutonomousCodingAgent

        @tool("custom", "Custom tool", {"arg": str})
        async def custom(args):
            return args["arg"]

        agent = AutonomousCodingAgent(backend="anthropic-sdk", tools=[custom])
        backend = agent._create_backend()

        # AnthropicSDKBackend stores tools as dict keyed by name
        assert "custom" in backend._extra_tools
        assert backend._extra_tools["custom"] is custom

    @pytest.mark.skipif(not HAS_CLAUDE_AGENT_SDK, reason="claude-agent-sdk not installed")
    def test_agent_passes_tools_to_claude_code_backend(self):
        """AutonomousCodingAgent should pass tools to ClaudeCodeBackend."""
        from agenter import AutonomousCodingAgent

        @tool("custom", "Custom tool", {"arg": str})
        async def custom(args):
            return args["arg"]

        agent = AutonomousCodingAgent(backend="claude-code", sandbox=False, tools=[custom])
        backend = agent._create_backend()

        assert backend._extra_tools == [custom]
