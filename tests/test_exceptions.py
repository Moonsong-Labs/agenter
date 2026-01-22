"""Tests for exception classes."""

import pytest

from agenter.data_models import (
    AgenterError,
    BackendError,
    BudgetExceededError,
    ConfigurationError,
    PathSecurityError,
    ToolExecutionError,
    ValidationError,
)


class TestExceptionHierarchy:
    """Test exception inheritance and common behavior."""

    def test_all_exceptions_inherit_from_sdkerror(self):
        """All SDK exceptions should inherit from AgenterError."""
        exception_classes = [
            BackendError,
            ValidationError,
            BudgetExceededError,
            ToolExecutionError,
            PathSecurityError,
            ConfigurationError,
        ]
        for exc_class in exception_classes:
            assert issubclass(exc_class, AgenterError)
            assert issubclass(exc_class, Exception)

    def test_all_exceptions_catchable_as_sdkerror(self):
        """All SDK exceptions should be catchable with a single except AgenterError."""
        errors = [
            AgenterError("base"),
            BackendError("backend"),
            ValidationError("validation"),
            BudgetExceededError("budget", limit_type="iterations", limit_value=5, actual_value=5),
            ToolExecutionError("tool", tool_name="test"),
            PathSecurityError("path", path="/etc"),
            ConfigurationError("config"),
        ]
        for error in errors:
            assert isinstance(error, AgenterError)
            assert error.message is not None
            assert str(error) == error.message


class TestBackendError:
    """Test BackendError with cause chaining."""

    def test_preserves_cause_chain(self):
        """BackendError should preserve the original exception cause."""
        original = ConnectionError("Network issue")
        error = BackendError("API failed", backend="anthropic-sdk", cause=original)
        assert error.cause is original
        assert error.backend == "anthropic-sdk"


class TestValidationError:
    """Test ValidationError with error list."""

    def test_captures_multiple_errors(self):
        """ValidationError should capture list of validation errors."""
        errors = ["Line 1: SyntaxError", "Line 5: IndentationError"]
        error = ValidationError("Validation failed", validator="SyntaxValidator", errors=errors)
        assert error.validator == "SyntaxValidator"
        assert error.errors == errors


class TestBudgetExceededError:
    """Test BudgetExceededError for different limit types."""

    @pytest.mark.parametrize("limit_type", ["iterations", "tokens", "cost", "time"])
    def test_captures_limit_details(self, limit_type):
        """BudgetExceededError should capture limit type and values."""
        error = BudgetExceededError(
            f"{limit_type} limit exceeded",
            limit_type=limit_type,
            limit_value=100,
            actual_value=150,
        )
        assert error.limit_type == limit_type
        assert error.limit_value == 100
        assert error.actual_value == 150


class TestPathSecurityError:
    """Test PathSecurityError path conversion."""

    def test_converts_path_objects_to_strings(self):
        """PathSecurityError should convert Path objects to strings."""
        from pathlib import Path

        error = PathSecurityError("Path violation", path=Path("/tmp/test.txt"), cwd=Path("/tmp"))
        assert error.path == "/tmp/test.txt"
        assert error.cwd == "/tmp"
        assert isinstance(error.path, str)
        assert isinstance(error.cwd, str)
