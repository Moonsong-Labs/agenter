"""Tests for the console display module."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from agenter.data_models import Verbosity
from agenter.runtime.display import LIMIT_ERRORS, ConsoleDisplay


class TestConsoleDisplayInit:
    """Test ConsoleDisplay initialization."""

    def test_quiet_mode_suppresses_console(self):
        """Quiet mode should not create a console."""
        display = ConsoleDisplay(verbosity=Verbosity.QUIET)
        assert display.console is None

    def test_non_quiet_modes_create_console(self):
        """Normal and verbose modes should create a console."""
        for verbosity in [Verbosity.NORMAL, Verbosity.VERBOSE]:
            display = ConsoleDisplay(verbosity=verbosity)
            assert display.console is not None

    def test_creates_output_dir_when_specified(self):
        """Output directory should be created if specified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "logs" / "run1"
            display = ConsoleDisplay(verbosity=Verbosity.NORMAL, output_dir=output_path)
            assert output_path.exists()
            assert display.output_dir == output_path


class TestConsoleDisplayPrint:
    """Test the _print method."""

    def test_quiet_mode_does_not_print(self):
        display = ConsoleDisplay(verbosity=Verbosity.QUIET)
        # Should not raise, just silently skip
        display._print("Hello")

    def test_normal_mode_prints(self):
        display = ConsoleDisplay(verbosity=Verbosity.NORMAL)
        display.console = MagicMock()
        display._print("Hello")
        display.console.print.assert_called_once_with("Hello")

    def test_verbose_mode_prints(self):
        display = ConsoleDisplay(verbosity=Verbosity.VERBOSE)
        display.console = MagicMock()
        display._print("Hello", style="bold")
        display.console.print.assert_called_once_with("Hello", style="bold")


class TestConsoleDisplaySaveToFile:
    """Test file saving functionality."""

    def test_saves_to_file_when_output_dir_set(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "logs"
            display = ConsoleDisplay(verbosity=Verbosity.NORMAL, output_dir=output_path)
            file_path = display._save_to_file("test.txt", "content")
            assert file_path is not None
            assert file_path.exists()
            assert file_path.read_text() == "content"

    def test_returns_none_when_no_output_dir(self):
        display = ConsoleDisplay(verbosity=Verbosity.NORMAL)
        result = display._save_to_file("test.txt", "content")
        assert result is None


class TestConsoleDisplayMethods:
    """Test display methods."""

    def test_verbose_mode_saves_prompt_to_file(self):
        """Verbose mode with output_dir should save prompts to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "logs"
            display = ConsoleDisplay(verbosity=Verbosity.VERBOSE, output_dir=output_path)
            display._print = MagicMock()
            display.display_prompt("User prompt", "System prompt")
            files = list(output_path.glob("*_prompt.txt"))
            assert len(files) == 1
            content = files[0].read_text()
            assert "System prompt" in content
            assert "User prompt" in content

    def test_validation_prints_errors_up_to_limit(self):
        """Validation should truncate errors beyond max_errors."""
        display = ConsoleDisplay(verbosity=Verbosity.NORMAL)
        display._print = MagicMock()
        errors = [f"Error {i}" for i in range(10)]
        display.report_validation(passed=False, errors=errors)
        # Should limit to max_errors + header + truncation message
        assert display._print.call_count <= LIMIT_ERRORS + 3


class TestConsoleDisplayFileLink:
    """Test file link generation."""

    def test_make_file_link(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "logs"
            display = ConsoleDisplay(verbosity=Verbosity.NORMAL, output_dir=output_path)
            link = display._make_file_link(output_path)
            assert "file://" in link
            assert "[link=" in link


class TestConsoleDisplayQuietMode:
    """Test that quiet mode suppresses all output."""

    def test_all_methods_work_in_quiet_mode(self):
        display = ConsoleDisplay(verbosity=Verbosity.QUIET)
        # All these should not raise
        display.start_session("/path", "model")
        display.start_iteration(1)
        display.display_prompt("prompt")
        display.display_response("response", 100)
        display.report_tool_call("tool", {})
        display.report_tool_result("tool", "result", True)
        display.report_validation(True, [])
        display.display_summary(True, 1, 100, {})


class TestConsoleDisplayVerboseMode:
    """Test verbose mode features."""

    def test_verbose_shows_tool_call_args(self):
        """Verbose mode should print tool call arguments in a Panel."""
        display = ConsoleDisplay(verbosity=Verbosity.VERBOSE)
        display._print = MagicMock()
        display.report_tool_call("read_file", {"path": "test.py", "content": "x" * 200})
        assert display._print.called


class TestConsoleDisplayWithOutputDir:
    """Test display with output directory for file logging."""

    def test_saves_prompts_and_responses_to_file(self):
        """With output_dir, prompts and responses should be saved to files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "logs"
            display = ConsoleDisplay(verbosity=Verbosity.VERBOSE, output_dir=output_path)
            display.display_prompt("Test prompt", "System prompt")
            display.display_response("Test response", 100)
            files = list(output_path.glob("*.txt"))
            assert len(files) >= 2  # At least prompt and response


class TestConsoleDisplayEdgeCases:
    """Test edge cases in display."""

    def test_empty_prompt_does_not_crash(self):
        """Empty prompt should be handled without crashing."""
        display = ConsoleDisplay(verbosity=Verbosity.NORMAL)
        display._print = MagicMock()
        display.display_prompt("")  # Should not raise

    def test_verbose_multiline_tool_result_shows_all_lines(self):
        """Verbose mode should show all lines of multiline tool result."""
        display = ConsoleDisplay(verbosity=Verbosity.VERBOSE)
        display._print = MagicMock()
        multiline_result = "line1\nline2\nline3\nline4\nline5"
        display.report_tool_result("read_file", multiline_result, True)
        # Should print header + content lines
        assert display._print.call_count >= 3
