"""Tests for framework adapters."""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, patch

import pytest

from agenter.adapters import langgraph, pydantic_ai
from agenter.coding_agent import AutonomousCodingAgent
from agenter.data_models import CodingResult, CodingStatus


def _has_langgraph() -> bool:
    """Check if langgraph/langchain-core is installed."""
    try:
        from langchain_core.runnables import RunnableLambda  # noqa: F401

        return True
    except ImportError:
        return False


def _has_pydantic_ai() -> bool:
    """Check if pydantic-ai is installed."""
    try:
        import pydantic_ai as pai  # noqa: F401

        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _has_langgraph(), reason="langchain-core not installed")
class TestLangGraphAdapter:
    """Tests for the LangGraph adapter."""

    def test_create_coding_node_returns_runnable(self):
        """create_coding_node should return a RunnableLambda."""
        from langchain_core.runnables import RunnableLambda

        node = langgraph.create_coding_node(cwd="/tmp")
        assert isinstance(node, RunnableLambda)

    def test_coding_state_is_typed_dict(self):
        """CodingState should be a TypedDict with expected keys."""
        assert "prompt" in langgraph.CodingState.__annotations__
        assert "cwd" in langgraph.CodingState.__annotations__
        assert "coding_result" in langgraph.CodingState.__annotations__

    @pytest.mark.asyncio
    async def test_coding_node_calls_agent_execute(self):
        """The node should call agent.execute() with correct args."""
        with patch.object(AutonomousCodingAgent, "execute", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = CodingResult(
                status=CodingStatus.COMPLETED,
                files={},
                summary="done",
                iterations=1,
            )

            node = langgraph.create_coding_node(cwd="/tmp")
            state = {"prompt": "write hello.py"}
            result = await node.ainvoke(state)

            mock_execute.assert_called_once()
            assert "coding_result" in result
            assert result["coding_result"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_coding_node_uses_state_cwd_over_default(self):
        """State cwd should override the default cwd."""
        with patch.object(AutonomousCodingAgent, "execute", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = CodingResult(
                status=CodingStatus.COMPLETED,
                files={},
                summary="done",
                iterations=1,
            )

            node = langgraph.create_coding_node(cwd="/default")
            state = {"prompt": "test", "cwd": "/override"}
            await node.ainvoke(state)

            call_args = mock_execute.call_args[0][0]
            assert call_args.cwd == "/override"

    @pytest.mark.asyncio
    async def test_coding_node_raises_without_cwd(self):
        """Node should raise if no cwd is provided."""
        node = langgraph.create_coding_node()  # No default cwd
        state = {"prompt": "test"}  # No cwd in state

        with pytest.raises(ValueError, match="cwd must be provided"):
            await node.ainvoke(state)


@pytest.mark.skipif(not _has_pydantic_ai(), reason="pydantic-ai not installed")
class TestPydanticAIAdapter:
    """Tests for the PydanticAI adapter."""

    def test_coding_agent_subclasses_agent(self):
        """CodingAgent should subclass pydantic_ai.Agent."""
        from pydantic_ai import Agent

        assert issubclass(pydantic_ai.CodingAgent, Agent)

    def test_coding_agent_init_signature(self):
        """CodingAgent should accept cwd and backend."""
        sig = inspect.signature(pydantic_ai.CodingAgent.__init__)
        params = list(sig.parameters.keys())
        assert "cwd" in params
        assert "backend" in params

    def test_coding_agent_run_signature(self):
        """CodingAgent.run should accept prompt."""
        sig = inspect.signature(pydantic_ai.CodingAgent.run)
        params = list(sig.parameters.keys())
        assert "prompt" in params

    def test_coding_agent_instantiation(self):
        """CodingAgent should instantiate with cwd."""
        agent = pydantic_ai.CodingAgent(cwd="/tmp")
        assert hasattr(agent, "run")
        assert hasattr(agent, "run_sync")

    def test_coding_tool_exists(self):
        """coding_tool function should be importable."""
        assert hasattr(pydantic_ai, "coding_tool")
