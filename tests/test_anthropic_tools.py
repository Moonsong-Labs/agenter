"""Tests for the Anthropic text editor tool."""

import tempfile
from pathlib import Path

import pytest

from agenter.coding_backends.anthropic_sdk.anthropic_tools import (
    ANTHROPIC_TEXT_EDITOR,
    AnthropicTextEditor,
)
from agenter.file_system import PathResolver


class TestAnthropicTextEditorDefinition:
    """Test the tool definition."""

    def test_tool_definition_structure(self):
        assert ANTHROPIC_TEXT_EDITOR["type"] == "text_editor_20250728"
        assert "name" in ANTHROPIC_TEXT_EDITOR


class TestAnthropicTextEditor:
    """Test AnthropicTextEditor class."""

    @pytest.fixture
    def editor(self):
        """Create editor with a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = PathResolver(Path(tmpdir))
            ed = AnthropicTextEditor(resolver)
            yield ed, Path(tmpdir)

    def test_cwd_property(self, editor):
        ed, tmpdir = editor
        assert ed.cwd.resolve() == tmpdir.resolve()

    def test_modified_files_empty(self, editor):
        ed, _ = editor
        assert ed.modified_files() == {}

    def test_reset(self, editor):
        ed, tmpdir = editor
        # Create a file to track
        (tmpdir / "test.txt").write_text("content")
        # Modify it through the editor
        ed._ops.write_file("test.txt", "new content", overwrite=True)
        assert len(ed.modified_files()) > 0
        ed.reset()
        assert len(ed.modified_files()) == 0


class TestAnthropicTextEditorExecute:
    """Test execute method."""

    @pytest.fixture
    def editor(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = PathResolver(Path(tmpdir))
            ed = AnthropicTextEditor(resolver)
            yield ed, Path(tmpdir)

    @pytest.mark.asyncio
    async def test_missing_command(self, editor):
        ed, _ = editor
        result = await ed.execute({})
        assert result.success is False
        assert "Missing 'command'" in result.output

    @pytest.mark.asyncio
    async def test_unknown_command(self, editor):
        ed, _ = editor
        result = await ed.execute({"command": "unknown_command"})
        assert result.success is False
        assert "Unknown command" in result.output


class TestAnthropicTextEditorView:
    """Test view command."""

    @pytest.fixture
    def editor(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = PathResolver(Path(tmpdir))
            ed = AnthropicTextEditor(resolver)
            yield ed, Path(tmpdir)

    @pytest.mark.asyncio
    async def test_view_missing_path(self, editor):
        ed, _ = editor
        result = await ed.execute({"command": "view"})
        assert result.success is False
        assert "Missing 'path'" in result.output

    @pytest.mark.asyncio
    async def test_view_file(self, editor):
        ed, tmpdir = editor
        (tmpdir / "test.txt").write_text("line1\nline2\nline3")
        result = await ed.execute({"command": "view", "path": "test.txt"})
        assert result.success is True
        assert "1: line1" in result.output
        assert "2: line2" in result.output
        assert "3: line3" in result.output

    @pytest.mark.asyncio
    async def test_view_file_with_range(self, editor):
        ed, tmpdir = editor
        (tmpdir / "test.txt").write_text("line1\nline2\nline3\nline4\nline5")
        result = await ed.execute({"command": "view", "path": "test.txt", "view_range": [2, 4]})
        assert result.success is True
        assert "2: line2" in result.output
        assert "3: line3" in result.output
        assert "4: line4" in result.output
        assert "1: line1" not in result.output

    @pytest.mark.asyncio
    async def test_view_directory(self, editor):
        ed, tmpdir = editor
        (tmpdir / "file1.py").touch()
        (tmpdir / "file2.txt").touch()
        (tmpdir / "subdir").mkdir()
        result = await ed.execute({"command": "view", "path": "."})
        assert result.success is True
        assert "file1.py" in result.output
        assert "file2.txt" in result.output

    @pytest.mark.asyncio
    async def test_view_nonexistent(self, editor):
        ed, _ = editor
        result = await ed.execute({"command": "view", "path": "nonexistent.txt"})
        assert result.success is False


class TestAnthropicTextEditorCreate:
    """Test create command."""

    @pytest.fixture
    def editor(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = PathResolver(Path(tmpdir))
            ed = AnthropicTextEditor(resolver)
            yield ed, Path(tmpdir)

    @pytest.mark.asyncio
    async def test_create_missing_path(self, editor):
        ed, _ = editor
        result = await ed.execute({"command": "create"})
        assert result.success is False
        assert "Missing 'path'" in result.output

    @pytest.mark.asyncio
    async def test_create_new_file(self, editor):
        ed, tmpdir = editor
        result = await ed.execute({"command": "create", "path": "new.txt", "file_text": "Hello, World!"})
        assert result.success is True
        assert (tmpdir / "new.txt").read_text() == "Hello, World!"

    @pytest.mark.asyncio
    async def test_create_empty_file(self, editor):
        ed, tmpdir = editor
        result = await ed.execute({"command": "create", "path": "empty.txt"})
        assert result.success is True
        assert (tmpdir / "empty.txt").exists()
        assert (tmpdir / "empty.txt").read_text() == ""

    @pytest.mark.asyncio
    async def test_create_existing_file_fails(self, editor):
        ed, tmpdir = editor
        (tmpdir / "existing.txt").write_text("original")
        result = await ed.execute({"command": "create", "path": "existing.txt", "file_text": "new"})
        assert result.success is False
        assert "already exists" in result.output


class TestAnthropicTextEditorStrReplace:
    """Test str_replace command."""

    @pytest.fixture
    def editor(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = PathResolver(Path(tmpdir))
            ed = AnthropicTextEditor(resolver)
            yield ed, Path(tmpdir)

    @pytest.mark.asyncio
    async def test_str_replace_missing_path(self, editor):
        ed, _ = editor
        result = await ed.execute({"command": "str_replace"})
        assert result.success is False
        assert "Missing 'path'" in result.output

    @pytest.mark.asyncio
    async def test_str_replace_missing_old_str(self, editor):
        ed, _ = editor
        result = await ed.execute({"command": "str_replace", "path": "test.txt"})
        assert result.success is False
        assert "Missing 'old_str'" in result.output

    @pytest.mark.asyncio
    async def test_str_replace_missing_new_str(self, editor):
        ed, _ = editor
        result = await ed.execute({"command": "str_replace", "path": "test.txt", "old_str": "old"})
        assert result.success is False
        assert "Missing 'new_str'" in result.output

    @pytest.mark.asyncio
    async def test_str_replace_success(self, editor):
        ed, tmpdir = editor
        (tmpdir / "test.txt").write_text("Hello, World!")
        result = await ed.execute(
            {
                "command": "str_replace",
                "path": "test.txt",
                "old_str": "World",
                "new_str": "Python",
            }
        )
        assert result.success is True
        assert (tmpdir / "test.txt").read_text() == "Hello, Python!"

    @pytest.mark.asyncio
    async def test_str_replace_not_found(self, editor):
        ed, tmpdir = editor
        (tmpdir / "test.txt").write_text("Hello, World!")
        result = await ed.execute(
            {
                "command": "str_replace",
                "path": "test.txt",
                "old_str": "Goodbye",
                "new_str": "Hi",
            }
        )
        assert result.success is False
        assert "No match found" in result.output

    @pytest.mark.asyncio
    async def test_str_replace_multiple_matches(self, editor):
        ed, tmpdir = editor
        (tmpdir / "test.txt").write_text("foo bar foo baz foo")
        result = await ed.execute(
            {
                "command": "str_replace",
                "path": "test.txt",
                "old_str": "foo",
                "new_str": "qux",
            }
        )
        assert result.success is False
        # Should indicate multiple matches


class TestAnthropicTextEditorInsert:
    """Test insert command."""

    @pytest.fixture
    def editor(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = PathResolver(Path(tmpdir))
            ed = AnthropicTextEditor(resolver)
            yield ed, Path(tmpdir)

    @pytest.mark.asyncio
    async def test_insert_missing_path(self, editor):
        ed, _ = editor
        result = await ed.execute({"command": "insert"})
        assert result.success is False
        assert "Missing 'path'" in result.output

    @pytest.mark.asyncio
    async def test_insert_missing_insert_line(self, editor):
        ed, _ = editor
        result = await ed.execute({"command": "insert", "path": "test.txt"})
        assert result.success is False
        assert "Missing 'insert_line'" in result.output

    @pytest.mark.asyncio
    async def test_insert_missing_new_str(self, editor):
        ed, _ = editor
        result = await ed.execute({"command": "insert", "path": "test.txt", "insert_line": 0})
        assert result.success is False
        assert "Missing 'new_str'" in result.output

    @pytest.mark.asyncio
    async def test_insert_at_beginning(self, editor):
        ed, tmpdir = editor
        (tmpdir / "test.txt").write_text("line1\nline2\n")
        result = await ed.execute(
            {
                "command": "insert",
                "path": "test.txt",
                "insert_line": 0,
                "new_str": "inserted\n",
            }
        )
        assert result.success is True
        content = (tmpdir / "test.txt").read_text()
        assert content.startswith("inserted\n")

    @pytest.mark.asyncio
    async def test_insert_in_middle(self, editor):
        ed, tmpdir = editor
        (tmpdir / "test.txt").write_text("line1\nline2\nline3\n")
        result = await ed.execute(
            {
                "command": "insert",
                "path": "test.txt",
                "insert_line": 1,
                "new_str": "inserted",
            }
        )
        assert result.success is True
        content = (tmpdir / "test.txt").read_text()
        lines = content.strip().split("\n")
        assert lines[1] == "inserted"


class TestAnthropicTextEditorSecurity:
    """Test security features in AnthropicTextEditor."""

    @pytest.fixture
    def editor(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = PathResolver(Path(tmpdir))
            ed = AnthropicTextEditor(resolver)
            yield ed, Path(tmpdir)

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, editor):
        """Test path traversal is blocked."""
        ed, _ = editor
        result = await ed.execute({"command": "view", "path": "../../../etc/passwd"})
        assert result.success is False

    @pytest.mark.asyncio
    async def test_create_with_write_restriction(self):
        """Test create fails when path not in allowed write paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = PathResolver(Path(tmpdir), allowed_write_paths=["*.txt"])
            ed = AnthropicTextEditor(resolver)
            result = await ed.execute(
                {
                    "command": "create",
                    "path": "test.py",  # Not allowed
                    "file_text": "content",
                }
            )
            assert result.success is False
