"""Tests for FileOperations utility class."""

import tempfile
from pathlib import Path

from agenter.data_models import ToolErrorCode, ToolResult
from agenter.file_system import FileOperations, PathResolver


class TestFileOperations:
    """Test FileOperations class."""

    def test_read_file_success(self):
        """FileOperations.read_file should return file contents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Hello, World!")

            resolver = PathResolver(Path(tmpdir))
            ops = FileOperations(resolver)

            result = ops.read_file("test.txt")
            assert result.success
            assert result.output == "Hello, World!"
            assert result.error is None

    def test_read_file_not_found(self):
        """FileOperations.read_file should fail for non-existent files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = PathResolver(Path(tmpdir))
            ops = FileOperations(resolver)

            result = ops.read_file("nonexistent.txt")
            assert not result.success
            assert "not found" in result.output.lower()
            assert result.error is not None
            assert result.error.code == ToolErrorCode.FILE_NOT_FOUND

    def test_write_file_success(self):
        """FileOperations.write_file should create a new file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = PathResolver(Path(tmpdir))
            ops = FileOperations(resolver)

            result = ops.write_file("new_file.txt", "Content here")
            assert result.success
            assert "Wrote" in result.output

            # Verify file was created
            assert (Path(tmpdir) / "new_file.txt").read_text() == "Content here"

            # Verify tracking
            assert "new_file.txt" in ops.files_modified
            assert ops.files_modified["new_file.txt"] == "Content here"

    def test_write_file_creates_directories(self):
        """FileOperations.write_file should create parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = PathResolver(Path(tmpdir))
            ops = FileOperations(resolver)

            result = ops.write_file("nested/dir/file.txt", "Content")
            assert result.success

            # Verify file was created with parent dirs
            assert (Path(tmpdir) / "nested" / "dir" / "file.txt").exists()

    def test_write_file_overwrite(self):
        """FileOperations.write_file with overwrite=True should replace existing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "existing.txt"
            test_file.write_text("Original")

            resolver = PathResolver(Path(tmpdir))
            ops = FileOperations(resolver)

            result = ops.write_file("existing.txt", "Updated", overwrite=True)
            assert result.success
            assert test_file.read_text() == "Updated"

    def test_write_file_no_overwrite(self):
        """FileOperations.write_file with overwrite=False should fail if exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "existing.txt"
            test_file.write_text("Original")

            resolver = PathResolver(Path(tmpdir))
            ops = FileOperations(resolver)

            result = ops.write_file("existing.txt", "Updated", overwrite=False)
            assert not result.success
            assert "already exists" in result.output

    def test_replace_string_success(self):
        """FileOperations.replace_string should replace unique string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("def hello():\n    return 'world'")

            resolver = PathResolver(Path(tmpdir))
            ops = FileOperations(resolver)

            result = ops.replace_string("test.py", "'world'", "'universe'")
            assert result.success
            assert test_file.read_text() == "def hello():\n    return 'universe'"

            # Verify tracking
            assert "test.py" in ops.files_modified

    def test_replace_string_not_found(self):
        """FileOperations.replace_string should fail if string not in file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("def hello():\n    return 'world'")

            resolver = PathResolver(Path(tmpdir))
            ops = FileOperations(resolver)

            result = ops.replace_string("test.py", "nonexistent", "replacement")
            assert not result.success
            assert "No match" in result.output
            assert result.error is not None
            assert result.error.code == ToolErrorCode.STRING_NOT_FOUND

    def test_replace_string_multiple_matches(self):
        """FileOperations.replace_string should fail if multiple matches."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("hello hello hello")

            resolver = PathResolver(Path(tmpdir))
            ops = FileOperations(resolver)

            result = ops.replace_string("test.py", "hello", "hi")
            assert not result.success
            assert "3 matches" in result.output
            assert result.error is not None
            assert result.error.code == ToolErrorCode.STRING_NOT_FOUND

    def test_list_directory_success(self):
        """FileOperations.list_directory should list directory contents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some files and dirs
            (Path(tmpdir) / "file1.txt").touch()
            (Path(tmpdir) / "file2.txt").touch()
            (Path(tmpdir) / "subdir").mkdir()

            resolver = PathResolver(Path(tmpdir))
            ops = FileOperations(resolver)

            result = ops.list_directory(".")
            assert result.success
            assert "file1.txt" in result.output
            assert "file2.txt" in result.output
            assert "subdir" in result.output

    def test_list_directory_not_found(self):
        """FileOperations.list_directory should fail for non-existent dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = PathResolver(Path(tmpdir))
            ops = FileOperations(resolver)

            result = ops.list_directory("nonexistent")
            assert not result.success
            assert "not found" in result.output.lower()

    def test_list_directory_not_a_directory(self):
        """FileOperations.list_directory should fail for files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "file.txt").touch()

            resolver = PathResolver(Path(tmpdir))
            ops = FileOperations(resolver)

            result = ops.list_directory("file.txt")
            assert not result.success
            assert "Not a directory" in result.output

    def test_files_modified_tracking(self):
        """FileOperations should track modified files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = PathResolver(Path(tmpdir))
            ops = FileOperations(resolver)

            # Initially empty
            assert ops.files_modified == {}

            # Write a file
            ops.write_file("a.txt", "content a")
            assert "a.txt" in ops.files_modified

            # Write another
            ops.write_file("b.txt", "content b")
            assert len(ops.files_modified) == 2

            # Reset clears tracking
            ops.reset()
            assert ops.files_modified == {}

    def test_check_exists_file(self):
        """FileOperations.check_exists should identify files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "test.txt").touch()

            resolver = PathResolver(Path(tmpdir))
            ops = FileOperations(resolver)

            result = ops.check_exists("test.txt")
            assert result.success
            assert result.output == "file"

    def test_check_exists_directory(self):
        """FileOperations.check_exists should identify directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "subdir").mkdir()

            resolver = PathResolver(Path(tmpdir))
            ops = FileOperations(resolver)

            result = ops.check_exists("subdir")
            assert result.success
            assert result.output == "directory"

    def test_check_exists_not_found(self):
        """FileOperations.check_exists should return 'not_found' for missing paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = PathResolver(Path(tmpdir))
            ops = FileOperations(resolver)

            result = ops.check_exists("nonexistent")
            assert result.success
            assert result.output == "not_found"

    def test_is_directory(self):
        """FileOperations.is_directory should correctly identify directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "file.txt").touch()
            (Path(tmpdir) / "subdir").mkdir()

            resolver = PathResolver(Path(tmpdir))
            ops = FileOperations(resolver)

            assert ops.is_directory("subdir") is True
            assert ops.is_directory("file.txt") is False
            assert ops.is_directory("nonexistent") is False

    def test_cwd_property(self):
        """FileOperations.cwd should return the working directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = PathResolver(Path(tmpdir))
            ops = FileOperations(resolver)

            assert ops.cwd == Path(tmpdir).resolve()


class TestToolResultFromError:
    """Test ToolResult.from_error factory used by FileOperations."""

    def test_from_error_creates_failed_result(self):
        """ToolResult.from_error should correctly associate error codes."""
        result = ToolResult.from_error(ToolErrorCode.FILE_NOT_FOUND, "test.txt")
        assert not result.success
        assert result.error.code == ToolErrorCode.FILE_NOT_FOUND
        assert result.error.message == "test.txt"


class TestFileOperationsEdgeCases:
    """Test edge cases in file operations not covered elsewhere."""

    def test_write_file_path_security_error(self):
        """Test write fails on path traversal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = PathResolver(Path(tmpdir), allowed_write_paths=["*.txt"])
            ops = FileOperations(resolver)

            # Try to write outside allowed paths
            result = ops.write_file("secret.py", "bad content")
            assert not result.success
            assert "not in allowed" in result.output.lower() or "error" in result.output.lower()

    def test_list_directory_with_depth(self):
        """Test listing directory with subdirectories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = PathResolver(Path(tmpdir))
            ops = FileOperations(resolver)

            # Create nested structure
            (Path(tmpdir) / "subdir").mkdir()
            (Path(tmpdir) / "subdir" / "nested.txt").write_text("content")
            (Path(tmpdir) / "top.txt").write_text("content")

            result = ops.list_directory(".", max_depth=2)
            assert result.success
            assert "subdir" in result.output

    def test_list_directory_hidden_files(self):
        """Test listing directory with hidden files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = PathResolver(Path(tmpdir))
            ops = FileOperations(resolver)

            (Path(tmpdir) / ".hidden").write_text("hidden")
            (Path(tmpdir) / "visible.txt").write_text("visible")

            # Without hidden
            result = ops.list_directory(".", include_hidden=False)
            assert "visible.txt" in result.output

            # With hidden
            result = ops.list_directory(".", include_hidden=True)
            assert result.success

    def test_replace_string_path_security(self):
        """Test replace_string with path outside allowed paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = PathResolver(Path(tmpdir), allowed_write_paths=["*.txt"])
            ops = FileOperations(resolver)

            (Path(tmpdir) / "test.py").write_text("hello world")

            result = ops.replace_string("test.py", "hello", "goodbye")
            assert not result.success

    def test_list_directory_path_security(self):
        """Test list_directory with path traversal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resolver = PathResolver(Path(tmpdir))
            ops = FileOperations(resolver)

            # Try to list parent directory
            result = ops.list_directory("../")
            assert not result.success
