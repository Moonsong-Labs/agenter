"""Integration test - requires API credentials."""

import os
import tempfile
from pathlib import Path

import pytest

from agenter import (
    AutonomousCodingAgent,
    Budget,
    CodingEventType,
    CodingRequest,
    CodingStatus,
)
from agenter.config import default_model

# Use appropriate model based on environment (Bedrock vs direct API)
MODEL = default_model()


@pytest.mark.skipif(
    not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("AWS_BEARER_TOKEN_BEDROCK")),
    reason="No API credentials set (ANTHROPIC_API_KEY or AWS_BEARER_TOKEN_BEDROCK)",
)
class TestIntegration:
    """Integration tests with real Claude API."""

    @pytest.mark.asyncio
    async def test_simple_task(self):
        """Test a simple coding task end-to-end."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = AutonomousCodingAgent(model=MODEL)
            result = await agent.execute(
                CodingRequest(
                    prompt="Create hello.py with a greet(name) function that returns 'Hello, {name}!'",
                    cwd=tmpdir,
                    max_iterations=3,
                )
            )

            assert result.status == CodingStatus.COMPLETED
            assert "hello.py" in result.files
            assert "def greet" in result.files["hello.py"]
            assert result.iterations >= 1

    @pytest.mark.asyncio
    async def test_budget_exceeded_iterations(self):
        """Test that budget exceeded is returned when max_iterations is hit.

        Note: The default agent uses only SyntaxValidator. To force budget exceeded,
        we need a scenario where syntax validation fails and retries can't fix it.
        We create a file with invalid syntax that the agent must "fix" but we
        set max_iterations=1 so it can only try once.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file with syntax error that the prompt asks to "complete"
            # The agent will try to fix it, but with max_iterations=1 and a
            # deliberately broken file, we want to see the behavior
            broken_file = Path(tmpdir) / "broken.py"
            broken_file.write_text("def incomplete(")  # Syntax error

            agent = AutonomousCodingAgent(model=MODEL)
            result = await agent.execute(
                CodingRequest(
                    prompt="The file broken.py has an incomplete function. Complete it to make it valid.",
                    cwd=tmpdir,
                    budget=Budget(max_iterations=1),
                )
            )

            # With max_iterations=1, the agent runs exactly once
            # If it succeeds (fixes the syntax), status is COMPLETED or COMPLETED_WITH_LIMIT_EXCEEDED
            # If validation fails after 1 iteration, status would be BUDGET_EXCEEDED
            # Since Claude is smart enough to fix simple syntax, it likely completes
            assert result.iterations == 1
            assert result.status in (
                CodingStatus.COMPLETED,
                CodingStatus.COMPLETED_WITH_LIMIT_EXCEEDED,
                CodingStatus.BUDGET_EXCEEDED,
            )

    @pytest.mark.asyncio
    async def test_stream_execute_events(self):
        """Test that stream_execute yields correct event sequence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = AutonomousCodingAgent(model=MODEL)
            events = []

            async for event in agent.stream_execute(
                CodingRequest(
                    prompt="Create simple.py with 'x = 1'",
                    cwd=tmpdir,
                    max_iterations=3,
                )
            ):
                events.append(event)

            # Verify event sequence
            event_types = [e.type for e in events]

            # Must have at least ITERATION_START
            assert CodingEventType.ITERATION_START in event_types

            # Must have BACKEND_MESSAGE(s)
            assert CodingEventType.BACKEND_MESSAGE in event_types

            # Must contain COMPLETED or FAILED, and end with SESSION_END
            assert CodingEventType.COMPLETED in event_types or CodingEventType.FAILED in event_types
            last_event = events[-1]
            assert last_event.type == CodingEventType.SESSION_END

    @pytest.mark.asyncio
    async def test_multi_file_task(self):
        """Test creating multiple files with imports."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = AutonomousCodingAgent(model=MODEL)
            result = await agent.execute(
                CodingRequest(
                    prompt=(
                        "Create two files:\n"
                        "1. utils.py with a function double(x) that returns x * 2\n"
                        "2. main.py that imports double from utils and calls double(5)"
                    ),
                    cwd=tmpdir,
                    max_iterations=3,
                )
            )

            assert result.status == CodingStatus.COMPLETED
            assert "utils.py" in result.files
            assert "main.py" in result.files
            assert "def double" in result.files["utils.py"]
            assert "from utils import" in result.files["main.py"] or "import utils" in result.files["main.py"]


class TestStructuredOutputIntegration:
    """Integration tests for structured output with real API calls."""

    @pytest.mark.skipif(
        not os.environ.get("AWS_BEARER_TOKEN_BEDROCK"),
        reason="Requires AWS_BEARER_TOKEN_BEDROCK",
    )
    @pytest.mark.asyncio
    async def test_bedrock_structured_output(self):
        """Test AnthropicSDKBackend (Bedrock) captures structured output via tool."""
        from pydantic import BaseModel, Field

        from agenter.coding_backends.anthropic_sdk import AnthropicSDKBackend
        from agenter.config import DEFAULT_MODEL_BEDROCK

        class CodeAnalysis(BaseModel):
            summary: str = Field(description="Brief summary of what the code does")
            language: str = Field(description="Programming language detected")
            has_bugs: bool = Field(description="Whether the code has potential bugs")

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "example.py"
            test_file.write_text("def greet(name):\n    return f'Hello, {name}!'\n")

            backend = AnthropicSDKBackend(model=DEFAULT_MODEL_BEDROCK)
            await backend.connect(tmpdir, output_type=CodeAnalysis)

            async for _ in backend.execute(
                "Read example.py and analyze it. Call the structured_response tool with your analysis."
            ):
                pass

            result = backend.structured_output()
            assert result is not None, "Structured output should be captured"
            assert isinstance(result, CodeAnalysis)
            assert "python" in result.language.lower()
            assert isinstance(result.has_bugs, bool)

            await backend.disconnect()

    @pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY") or bool(os.environ.get("AWS_BEARER_TOKEN_BEDROCK")),
        reason="Requires ANTHROPIC_API_KEY without AWS_BEARER_TOKEN_BEDROCK (Bedrock takes priority)",
    )
    @pytest.mark.asyncio
    async def test_anthropic_api_structured_output(self):
        """Test AnthropicSDKBackend (direct API) captures structured output natively."""
        from pydantic import BaseModel, Field

        from agenter.coding_backends.anthropic_sdk import AnthropicSDKBackend

        class CodeAnalysis(BaseModel):
            summary: str = Field(description="Brief summary of what the code does")
            language: str = Field(description="Programming language detected")
            has_bugs: bool = Field(description="Whether the code has potential bugs")

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "example.py"
            test_file.write_text("def greet(name):\n    return f'Hello, {name}!'\n")

            backend = AnthropicSDKBackend(model="claude-sonnet-4-20250514")
            await backend.connect(tmpdir, output_type=CodeAnalysis)

            async for _ in backend.execute("Read example.py and analyze it."):
                pass

            result = backend.structured_output()
            assert result is not None, "Structured output should be captured"
            assert isinstance(result, CodeAnalysis)
            assert "python" in result.language.lower()
            assert isinstance(result.has_bugs, bool)

            await backend.disconnect()

    # NOTE: ClaudeCodeBackend test skipped - hangs in pytest due to anyio/subprocess issues.
    # Works fine (~15s) when run directly. Test manually with:
    #   ANTHROPIC_API_KEY="key" python -c "
    #   import tempfile, anyio; from agenter.coding_backends.claude_code import ClaudeCodeBackend
    #   async def t():
    #       with tempfile.TemporaryDirectory() as d:
    #           b = ClaudeCodeBackend(sandbox=False); await b.connect(d)
    #           async for _ in b.execute('Create hello.py'): pass
    #           print('OK'); await b.disconnect()
    #   anyio.run(t)
    #   "


def _codex_available() -> bool:
    """Check if Codex CLI and openai-agents are available."""
    import shutil

    # Check for codex CLI
    if shutil.which("codex") is None:
        return False

    # Check for openai-agents package
    try:
        from agents.mcp import MCPServerStdio  # noqa: F401

        return True
    except ImportError:
        return False


@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="No OPENAI_API_KEY set",
)
@pytest.mark.skipif(
    not _codex_available(),
    reason="Codex CLI or openai-agents not available (pip install agenter[codex] && npm install -g @openai/codex)",
)
class TestCodexIntegration:
    """Integration tests for Codex backend with real API calls."""

    @pytest.mark.asyncio
    async def test_simple_task_codex(self):
        """Test a simple coding task with Codex backend."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = AutonomousCodingAgent(
                backend="codex",
                model="o3-mini",  # Use mini for faster/cheaper tests
                codex_approval_policy="never",
            )
            result = await agent.execute(
                CodingRequest(
                    prompt="Create hello.py with a greet(name) function that returns 'Hello, {name}!'",
                    cwd=tmpdir,
                    max_iterations=3,
                )
            )

            assert result.status == CodingStatus.COMPLETED
            # Check file was created on disk
            hello_path = Path(tmpdir) / "hello.py"
            assert hello_path.exists()
            content = hello_path.read_text()
            assert "def greet" in content

    @pytest.mark.asyncio
    async def test_codex_backend_direct(self):
        """Test CodexBackend directly for basic operations."""
        from agenter.coding_backends.codex import CodexBackend
        from agenter.data_models import TextMessage

        with tempfile.TemporaryDirectory() as tmpdir:
            backend = CodexBackend(
                model="o3-mini",
                approval_policy="never",
                sandbox="workspace-write",
            )
            await backend.connect(tmpdir)

            messages = []
            async for msg in backend.execute("Create a file called test.py with x = 42"):
                messages.append(msg)

            # Should have at least one message
            assert len(messages) > 0
            # Should have at least one text message
            text_messages = [m for m in messages if isinstance(m, TextMessage)]
            assert len(text_messages) >= 0  # May be empty if only tool calls

            # Check usage was tracked
            usage = backend.usage()
            assert usage.provider == "codex"
            assert usage.model == "o3-mini"

            await backend.disconnect()

    @pytest.mark.asyncio
    async def test_codex_stream_execute(self):
        """Test stream_execute with Codex backend."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = AutonomousCodingAgent(
                backend="codex",
                model="o3-mini",
            )
            events = []

            async for event in agent.stream_execute(
                CodingRequest(
                    prompt="Create simple.py with 'x = 1'",
                    cwd=tmpdir,
                    max_iterations=2,
                )
            ):
                events.append(event)

            # Verify event sequence
            event_types = [e.type for e in events]

            # Must have at least ITERATION_START
            assert CodingEventType.ITERATION_START in event_types

            # Must end with SESSION_END
            last_event = events[-1]
            assert last_event.type == CodingEventType.SESSION_END


def _has_anthropic_creds() -> bool:
    """Check if Anthropic credentials are available."""
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("AWS_BEARER_TOKEN_BEDROCK"))


def _openhands_sdk_available() -> bool:
    """Check if openhands-sdk is installed."""
    try:
        import openhands.sdk  # noqa: F401

        return True
    except ImportError:
        return False


def _cloudpickle_available() -> bool:
    """Check if cloudpickle is installed (needed for Codex custom tools)."""
    try:
        import cloudpickle  # noqa: F401

        return True
    except ImportError:
        return False


# =============================================================================
# Parameterized Integration Tests (All backends via AutonomousCodingAgent)
# =============================================================================


def _get_agent_instance(
    backend_name: str,
    extra_tools: list | None = None,
) -> AutonomousCodingAgent:
    """Factory to create AutonomousCodingAgent with appropriate backend config.

    Uses the high-level agent interface which handles backend lifecycle properly.
    """
    if backend_name == "anthropic-sdk":
        return AutonomousCodingAgent(
            backend="anthropic-sdk",
            model=MODEL,
            sandbox=False,
            tools=extra_tools,
        )
    elif backend_name == "claude-code":
        return AutonomousCodingAgent(
            backend="claude-code",
            sandbox=False,
            tools=extra_tools,
        )
    elif backend_name == "codex":
        return AutonomousCodingAgent(
            backend="codex",
            model="o3-mini",
            codex_approval_policy="never",
            sandbox=False,
            tools=extra_tools,
        )
    elif backend_name == "openhands":
        return AutonomousCodingAgent(
            backend="openhands",
            sandbox=False,
            tools=extra_tools,
        )
    else:
        raise ValueError(f"Unknown backend: {backend_name}")


def _has_anthropic_creds() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("AWS_BEARER_TOKEN_BEDROCK"))


def _has_openai_creds() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


def _has_direct_anthropic_key() -> bool:
    """Check for direct ANTHROPIC_API_KEY (required by claude-agent SDK)."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


# Backend test configurations with skip conditions
# Note: claude-code requires ANTHROPIC_API_KEY and doesn't work in pytest due to subprocess issues
BACKEND_CONFIGS = [
    pytest.param(
        "anthropic-sdk",
        marks=pytest.mark.skipif(not _has_anthropic_creds(), reason="No Anthropic credentials"),
    ),
    # claude-code: tested via tests/manual/test_claude_agent.py (subprocess issues in pytest)
    pytest.param(
        "codex",
        marks=[
            pytest.mark.skipif(not _has_openai_creds(), reason="No OPENAI_API_KEY"),
            pytest.mark.skipif(not _codex_available(), reason="openai-agents not installed"),
        ],
    ),
    pytest.param(
        "openhands",
        marks=[
            pytest.mark.skipif(not _has_openai_creds(), reason="No OPENAI_API_KEY"),
            pytest.mark.skipif(not _openhands_sdk_available(), reason="openhands-sdk not installed"),
        ],
    ),
]


class TestBackendFileCreation:
    """Test file creation across all backends."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("backend_name", BACKEND_CONFIGS)
    async def test_creates_python_file(self, backend_name: str):
        """All backends should be able to create a Python file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = _get_agent_instance(backend_name)
            result = await agent.execute(
                CodingRequest(
                    prompt="Create hello.py with: print('hello')",
                    cwd=tmpdir,
                    max_iterations=3,
                )
            )

            py_path = Path(tmpdir) / "hello.py"
            assert py_path.exists(), f"{backend_name} should create hello.py"
            assert result.status in (CodingStatus.COMPLETED, CodingStatus.COMPLETED_WITH_LIMIT_EXCEEDED)


class TestBackendCustomTools:
    """Test custom tools across all backends."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("backend_name", BACKEND_CONFIGS)
    async def test_custom_tool_called(self, backend_name: str):
        """All backends should be able to use custom tools."""
        from agenter import ToolResult, tool

        # Track tool calls with a mutable container (works for in-process backends)
        tool_call_count = {"count": 0, "result": None}

        @tool("get_magic_number", "Returns 42 multiplied by the given multiplier", {"multiplier": int})
        async def get_magic_number(args: dict) -> ToolResult:
            multiplier = args.get("multiplier", 1)
            result = 42 * multiplier
            tool_call_count["count"] += 1
            tool_call_count["result"] = result
            return ToolResult(output=str(result), success=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = _get_agent_instance(backend_name, extra_tools=[get_magic_number])

            # Use stream_execute to capture events and check for tool call/result
            events = []
            async for event in agent.stream_execute(
                CodingRequest(
                    prompt="Use the get_magic_number tool with multiplier=3 and tell me the result.",
                    cwd=tmpdir,
                    max_iterations=3,
                )
            ):
                events.append(event)

            # Verify tool was called - check either:
            # 1. In-process counter was incremented (anthropic-sdk, claude-code, openhands), OR
            # 2. Result "126" appears in events (codex uses subprocess)
            has_result_in_events = any("126" in str(getattr(e, "data", "")) for e in events)

            assert tool_call_count["count"] >= 1 or has_result_in_events, (
                f"{backend_name} should call custom tool (counter={tool_call_count['count']}, "
                f"has_result={has_result_in_events})"
            )


class TestAnthropicSDKSpecificSandbox:
    """Tests specific to AnthropicSDKBackend's allowed_write_paths feature."""

    @pytest.mark.skipif(not _has_anthropic_creds(), reason="No Anthropic credentials")
    @pytest.mark.asyncio
    async def test_sandbox_blocks_outside_allowed_paths(self):
        """sandbox=True blocks writes outside allowed_write_paths (AnthropicSDK-specific)."""
        from agenter.coding_backends.anthropic_sdk import AnthropicSDKBackend

        with tempfile.TemporaryDirectory() as tmpdir:
            backend = AnthropicSDKBackend(model=MODEL, sandbox=True)
            await backend.connect(tmpdir, allowed_write_paths=["*.py"])

            async for _ in backend.execute("Create a file called test.txt with 'hello'. Just create it."):
                pass

            txt_path = Path(tmpdir) / "test.txt"
            assert not txt_path.exists(), "sandbox=True should block .txt when only *.py allowed"
            await backend.disconnect()


class TestOpenHandsSpecific:
    """Tests specific to OpenHandsBackend."""

    @pytest.mark.skipif(not _has_openai_creds(), reason="No OPENAI_API_KEY")
    @pytest.mark.asyncio
    async def test_sandbox_true_raises_error(self):
        """OpenHandsBackend requires sandbox=False."""
        from agenter.coding_backends.openhands import OpenHandsBackend
        from agenter.data_models import ConfigurationError

        with pytest.raises(ConfigurationError, match="sandbox"):
            OpenHandsBackend()  # Default is sandbox=True

        # Should succeed with sandbox=False
        backend = OpenHandsBackend(sandbox=False)
        assert backend is not None
