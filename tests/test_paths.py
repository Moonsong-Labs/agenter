"""Tests for PathResolver pattern matching semantics."""

from pathlib import Path

import pytest

from agenter.file_system import PathResolver


class TestPathResolverWriteAllowed:
    """Test is_write_allowed pattern matching.

    These tests document the gitignore-style glob semantics provided by pathspec.
    Patterns are anchored to the working directory root.
    """

    def test_star_pattern_matches_root_only(self):
        """'*.py' matches files only at the root level (root-anchored)."""
        resolver = PathResolver(Path("/project"), ["*.py"])
        # Only root level .py files match
        assert resolver.is_write_allowed(Path("/project/foo.py"))
        # Nested files don't match (not right-anchored anymore)
        assert not resolver.is_write_allowed(Path("/project/src/foo.py"))
        assert not resolver.is_write_allowed(Path("/project/a/b/c/foo.py"))
        # Non-.py files don't match
        assert not resolver.is_write_allowed(Path("/project/foo.txt"))

    def test_directory_star_pattern_root_anchored(self):
        """'src/*.py' matches .py files directly under src/ at root."""
        resolver = PathResolver(Path("/project"), ["src/*.py"])
        # Matches src/ at root level only
        assert resolver.is_write_allowed(Path("/project/src/foo.py"))
        # Does NOT match src/ at other levels (root-anchored)
        assert not resolver.is_write_allowed(Path("/project/other/src/foo.py"))
        # Doesn't match nested directories under src
        assert not resolver.is_write_allowed(Path("/project/src/sub/foo.py"))
        # And doesn't match non-.py files
        assert not resolver.is_write_allowed(Path("/project/src/foo.txt"))

    def test_recursive_pattern(self):
        """'src/**/*.py' matches .py files at any depth under src/.

        With pathspec (gitwildmatch), ** matches zero or more directories,
        so 'src/**/*.py' matches 'src/foo.py', 'src/sub/bar.py', and deeper.
        """
        resolver = PathResolver(Path("/project"), ["src/**/*.py"])
        # ** allows zero or more intermediate directories
        assert resolver.is_write_allowed(Path("/project/src/foo.py"))
        assert resolver.is_write_allowed(Path("/project/src/sub/bar.py"))
        assert resolver.is_write_allowed(Path("/project/src/a/b/baz.py"))
        # Doesn't match files not under src
        assert not resolver.is_write_allowed(Path("/project/foo.py"))
        assert not resolver.is_write_allowed(Path("/project/other/foo.py"))

    def test_none_allows_all(self):
        """None allowed_write_paths allows all writes."""
        resolver = PathResolver(Path("/project"), None)
        assert resolver.is_write_allowed(Path("/project/any/path/file.txt"))
        assert resolver.is_write_allowed(Path("/project/foo.py"))
        assert resolver.is_write_allowed(Path("/project/deeply/nested/file.xyz"))

    def test_empty_list_allows_nothing(self):
        """Empty list of patterns allows no writes."""
        resolver = PathResolver(Path("/project"), [])
        assert not resolver.is_write_allowed(Path("/project/foo.py"))
        assert not resolver.is_write_allowed(Path("/project/any/file.txt"))

    def test_multiple_patterns(self):
        """Multiple patterns use OR logic."""
        resolver = PathResolver(Path("/project"), ["*.py", "*.md"])
        # Root level files match
        assert resolver.is_write_allowed(Path("/project/foo.py"))
        assert resolver.is_write_allowed(Path("/project/README.md"))
        # Nested files don't match with just *.ext patterns
        assert not resolver.is_write_allowed(Path("/project/src/bar.py"))
        assert not resolver.is_write_allowed(Path("/project/docs/guide.md"))
        # Other extensions don't match
        assert not resolver.is_write_allowed(Path("/project/foo.txt"))
        assert not resolver.is_write_allowed(Path("/project/data.json"))

    def test_double_star_pattern(self):
        """'**/*.py' matches .py files at any depth including root.

        With pathspec (gitwildmatch), **/ matches zero or more directories,
        so '**/*.py' matches 'foo.py' at root and 'dir/foo.py' and deeper.
        """
        resolver = PathResolver(Path("/project"), ["**/*.py"])
        # ** matches zero or more directories, so root is included
        assert resolver.is_write_allowed(Path("/project/foo.py"))
        assert resolver.is_write_allowed(Path("/project/src/bar.py"))
        assert resolver.is_write_allowed(Path("/project/a/b/c/d/e.py"))
        assert not resolver.is_write_allowed(Path("/project/foo.txt"))

    def test_question_mark_pattern(self):
        """'?' matches any single character."""
        resolver = PathResolver(Path("/project"), ["?.py"])
        assert resolver.is_write_allowed(Path("/project/a.py"))
        # Root-anchored, so nested files don't match
        assert not resolver.is_write_allowed(Path("/project/src/b.py"))
        assert not resolver.is_write_allowed(Path("/project/ab.py"))
        assert not resolver.is_write_allowed(Path("/project/foo.py"))

    def test_character_class_pattern(self):
        """'[seq]' matches any character in seq."""
        resolver = PathResolver(Path("/project"), ["[abc].py"])
        assert resolver.is_write_allowed(Path("/project/a.py"))
        assert resolver.is_write_allowed(Path("/project/b.py"))
        assert resolver.is_write_allowed(Path("/project/c.py"))
        assert not resolver.is_write_allowed(Path("/project/d.py"))

    def test_tests_directory_pattern(self):
        """'tests/**' matches everything under tests/ at any depth.

        With pathspec (gitwildmatch), ** matches zero or more directories,
        so 'tests/**' matches all files under tests/ recursively.
        """
        resolver = PathResolver(Path("/project"), ["tests/**"])
        assert resolver.is_write_allowed(Path("/project/tests/test_foo.py"))
        # ** matches any depth
        assert resolver.is_write_allowed(Path("/project/tests/unit/test_bar.py"))
        assert resolver.is_write_allowed(Path("/project/tests/conftest.py"))
        # Root-anchored, so only matches tests/ at root
        assert not resolver.is_write_allowed(Path("/project/other/tests/test.py"))

    def test_specific_file_pattern(self):
        """Specific file patterns work (root-anchored)."""
        resolver = PathResolver(Path("/project"), ["README.md", "setup.py"])
        assert resolver.is_write_allowed(Path("/project/README.md"))
        assert resolver.is_write_allowed(Path("/project/setup.py"))
        # Root-anchored: doesn't match nested files
        assert not resolver.is_write_allowed(Path("/project/docs/README.md"))
        assert not resolver.is_write_allowed(Path("/project/other.md"))


class TestPathResolverResolve:
    """Test path resolution security."""

    def test_resolve_relative_path(self):
        """Relative paths are resolved relative to cwd."""
        resolver = PathResolver(Path("/project"))
        resolved = resolver.resolve("src/main.py")
        assert resolved == Path("/project/src/main.py")

    def test_resolve_absolute_path_within_cwd(self):
        """Absolute paths within cwd are allowed."""
        resolver = PathResolver(Path("/project"))
        resolved = resolver.resolve("/project/src/main.py")
        assert resolved == Path("/project/src/main.py")

    def test_resolve_blocks_directory_traversal(self):
        """Directory traversal attacks are blocked."""
        from agenter.data_models import PathSecurityError

        resolver = PathResolver(Path("/project"))
        with pytest.raises(PathSecurityError) as exc_info:
            resolver.resolve("../secret.txt")
        assert exc_info.value.reason == "directory_traversal"

    def test_resolve_blocks_absolute_path_outside_cwd(self):
        """Absolute paths outside cwd are blocked."""
        from agenter.data_models import PathSecurityError

        resolver = PathResolver(Path("/project"))
        with pytest.raises(PathSecurityError) as exc_info:
            resolver.resolve("/etc/passwd")
        assert exc_info.value.reason == "directory_traversal"

    def test_resolve_and_check_write_success(self):
        """resolve_and_check_write succeeds for allowed paths."""
        resolver = PathResolver(Path("/project"), ["**/*.py"])
        resolved = resolver.resolve_and_check_write("src/main.py")
        assert resolved == Path("/project/src/main.py")

    def test_resolve_and_check_write_blocked(self):
        """resolve_and_check_write fails for non-allowed paths."""
        from agenter.data_models import PathSecurityError

        resolver = PathResolver(Path("/project"), ["**/*.py"])
        with pytest.raises(PathSecurityError) as exc_info:
            resolver.resolve_and_check_write("data.json")
        assert exc_info.value.reason == "write_restricted"
