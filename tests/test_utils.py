"""Tests for utility modules."""

from agenter.coding_backends.retry import build_retry_prompt
from agenter.pricing import calculate_cost_usd


class TestCalculateCostUsd:
    """Test the calculate_cost_usd function."""

    def test_returns_float(self):
        """Cost calculation should always return a float."""
        cost = calculate_cost_usd("claude-sonnet-4-20250514", 1000, 500)
        assert isinstance(cost, float)
        assert cost >= 0.0

    def test_never_raises_on_unknown_model(self):
        """Unknown models should return 0 cost without raising."""
        cost = calculate_cost_usd("unknown-model-xyz", 1000, 500)
        assert cost >= 0.0

    def test_zero_tokens_zero_cost(self):
        """Zero tokens should always return zero cost."""
        cost = calculate_cost_usd("claude-sonnet-4-20250514", 0, 0)
        assert cost == 0.0


class TestBuildRetryPrompt:
    """Test the build_retry_prompt function."""

    def test_formats_single_error(self):
        prompt = build_retry_prompt("Original prompt", ["Syntax error on line 1"], [])
        assert "Syntax error on line 1" in prompt
        assert "Original prompt" in prompt

    def test_formats_multiple_errors(self):
        errors = ["Error 1", "Error 2", "Error 3"]
        prompt = build_retry_prompt("Task", errors, [])
        for error in errors:
            assert error in prompt

    def test_empty_errors(self):
        prompt = build_retry_prompt("Task", [], [])
        # Should return original prompt
        assert prompt == "Task"

    def test_includes_tool_failures(self):
        prompt = build_retry_prompt("Task", [], ["Tool X failed"])
        assert "Tool X failed" in prompt

    def test_includes_both_errors_and_failures(self):
        prompt = build_retry_prompt("Task", ["Validation error"], ["Tool failure"])
        assert "Validation error" in prompt
        assert "Tool failure" in prompt
