"""Tests for the file tools module (coding_backends/anthropic_sdk/file_tools.py)."""

import tempfile
from pathlib import Path

import pytest

from agenter.coding_backends.anthropic_sdk.file_tools import FILE_TOOLS, FileTools
from agenter.data_models import ToolErrorCode
from agenter.file_system import PathResolver


class TestFileToolsDefinitions:
    """Test file tool definitions."""

    def test_all_tools_have_required_fields(self):
        """All file tools should have description and input_schema."""
        assert len(FILE_TOOLS) == 4
        expected_tools = {"read_file", "write_file", "edit_file", "list_files"}
        actual_tools = {t["name"] for t in FILE_TOOLS}
        assert actual_tools == expected_tools
        for tool in FILE_TOOLS:
            assert tool["description"]
            assert "properties" in tool["input_schema"]


class TestFileToolsExecutor:
    """Test FileTools executor."""

    @pytest.fixture
    def file_tools(self):
        """Create FileTools with a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = PathResolver(Path(tmpdir))
            tools = FileTools(resolver)
            yield tools, Path(tmpdir)

    @pytest.mark.asyncio
    async def test_read_file_success(self, file_tools):
        tools, tmpdir = file_tools
        # Create a test file
        test_file = tmpdir / "test.txt"
        test_file.write_text("Hello, World!")

        result = await tools.execute("read_file", {"path": "test.txt"})
        assert result.success is True
        assert result.output == "Hello, World!"

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, file_tools):
        tools, _tmpdir = file_tools
        result = await tools.execute("read_file", {"path": "nonexistent.txt"})
        assert result.success is False
        assert result.error is not None
        assert result.error.code == ToolErrorCode.FILE_NOT_FOUND

    @pytest.mark.asyncio
    async def test_write_file_success(self, file_tools):
        tools, tmpdir = file_tools
        result = await tools.execute("write_file", {"path": "new.txt", "content": "New content"})
        assert result.success is True
        # Verify file was created
        assert (tmpdir / "new.txt").read_text() == "New content"

    @pytest.mark.asyncio
    async def test_write_file_tracks_modification(self, file_tools):
        tools, _tmpdir = file_tools
        await tools.execute("write_file", {"path": "tracked.txt", "content": "content"})
        modified = tools.modified_files()
        assert "tracked.txt" in modified

    @pytest.mark.asyncio
    async def test_edit_file_success(self, file_tools):
        tools, tmpdir = file_tools
        # Create a file to edit
        test_file = tmpdir / "edit.txt"
        test_file.write_text("Hello, World!")

        result = await tools.execute(
            "edit_file",
            {"path": "edit.txt", "old_string": "World", "new_string": "Python"},
        )
        assert result.success is True
        assert test_file.read_text() == "Hello, Python!"

    @pytest.mark.asyncio
    async def test_edit_file_string_not_found(self, file_tools):
        tools, tmpdir = file_tools
        test_file = tmpdir / "edit.txt"
        test_file.write_text("Hello, World!")

        result = await tools.execute(
            "edit_file",
            {"path": "edit.txt", "old_string": "Goodbye", "new_string": "Hi"},
        )
        assert result.success is False
        assert "not found" in result.output.lower()

    @pytest.mark.asyncio
    async def test_edit_file_multiple_matches(self, file_tools):
        tools, tmpdir = file_tools
        test_file = tmpdir / "edit.txt"
        test_file.write_text("foo bar foo baz foo")

        result = await tools.execute(
            "edit_file",
            {"path": "edit.txt", "old_string": "foo", "new_string": "qux"},
        )
        assert result.success is False
        assert "ambiguous" in result.output.lower() or "multiple" in result.output.lower()

    @pytest.mark.asyncio
    async def test_list_files_success(self, file_tools):
        tools, tmpdir = file_tools
        # Create some files and directories
        (tmpdir / "file1.py").touch()
        (tmpdir / "file2.txt").touch()
        (tmpdir / "subdir").mkdir()

        result = await tools.execute("list_files", {"path": "."})
        assert result.success is True
        assert "file1.py" in result.output
        assert "file2.txt" in result.output
        assert "subdir" in result.output

    @pytest.mark.asyncio
    async def test_list_files_empty_directory(self, file_tools):
        tools, tmpdir = file_tools
        (tmpdir / "empty").mkdir()

        result = await tools.execute("list_files", {"path": "empty"})
        assert result.success is True
        assert "empty" in result.output.lower()

    @pytest.mark.asyncio
    async def test_list_files_not_found(self, file_tools):
        tools, _tmpdir = file_tools
        result = await tools.execute("list_files", {"path": "nonexistent"})
        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_list_files_not_a_directory(self, file_tools):
        tools, tmpdir = file_tools
        (tmpdir / "file.txt").touch()

        result = await tools.execute("list_files", {"path": "file.txt"})
        assert result.success is False
        assert "not a directory" in result.output.lower()

    @pytest.mark.asyncio
    async def test_unknown_tool(self, file_tools):
        tools, _tmpdir = file_tools
        result = await tools.execute("unknown_tool", {})
        assert result.success is False
        assert result.error is not None
        assert result.error.code == ToolErrorCode.UNKNOWN_TOOL

    @pytest.mark.asyncio
    async def test_missing_required_parameter(self, file_tools):
        tools, _tmpdir = file_tools
        result = await tools.execute("read_file", {})
        assert result.success is False
        assert "missing" in result.output.lower()

    @pytest.mark.asyncio
    async def test_path_security_error(self, file_tools):
        tools, _tmpdir = file_tools
        result = await tools.execute("read_file", {"path": "../../../etc/passwd"})
        assert result.success is False
        assert result.error is not None
        assert result.error.code == ToolErrorCode.PATH_SECURITY

    @pytest.mark.asyncio
    async def test_reset_clears_modified_files(self, file_tools):
        tools, _tmpdir = file_tools
        await tools.execute("write_file", {"path": "test.txt", "content": "content"})
        assert len(tools.modified_files()) > 0

        tools.reset()
        assert len(tools.modified_files()) == 0

    def test_cwd_property(self, file_tools):
        tools, tmpdir = file_tools
        # Use resolve() to handle macOS /var -> /private/var symlink
        assert tools.cwd.resolve() == tmpdir.resolve()

    @pytest.mark.asyncio
    async def test_list_files_shows_file_type_prefix(self, file_tools):
        tools, tmpdir = file_tools
        (tmpdir / "file.py").touch()
        (tmpdir / "subdir").mkdir()

        result = await tools.execute("list_files", {"path": "."})
        assert result.success is True
        # Should show "f " for files and "d " for directories
        assert "f file.py" in result.output or "f  file.py" in result.output.replace("  ", " ")
        assert "d subdir" in result.output or "d  subdir" in result.output.replace("  ", " ")


class TestFileToolsEdgeCases:
    """Test edge cases in FileTools."""

    @pytest.mark.asyncio
    async def test_write_file_creates_parent_dirs(self):
        """Test write_file creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = PathResolver(Path(tmpdir))
            tools = FileTools(resolver)
            result = await tools.execute(
                "write_file",
                {
                    "path": "nested/dir/file.txt",
                    "content": "hello",
                },
            )
            assert result.success is True
            assert (Path(tmpdir) / "nested" / "dir" / "file.txt").exists()

    @pytest.mark.asyncio
    async def test_write_file_with_restriction(self):
        """Test write_file with path restriction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = PathResolver(Path(tmpdir), allowed_write_paths=["*.txt"])
            tools = FileTools(resolver)
            result = await tools.execute(
                "write_file",
                {
                    "path": "test.py",  # Not allowed
                    "content": "print('hello')",
                },
            )
            assert result.success is False
