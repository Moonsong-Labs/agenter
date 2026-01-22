"""File system utilities - path resolution, security, and file operations.

This module provides secure path handling and file operations within
a constrained working directory.

Example:
    from agenter.file_system import PathResolver, FileOperations

    resolver = PathResolver(
        cwd=Path("/project"),
        allowed_write_paths=["src/**/*.py", "tests/**"]
    )

    ops = FileOperations(resolver)
    result = ops.read_file("src/main.py")
    if result.success:
        print(result.output)
"""

from __future__ import annotations

from pathlib import Path

import pathspec

from .data_models import PathSecurityError, ToolErrorCode, ToolResult


class PathResolver:
    """Secure path resolution within a working directory.

    This class handles path resolution with security checks to prevent
    directory traversal attacks and enforce write restrictions.

    Args:
        cwd: The working directory. All paths are resolved relative to this.
        allowed_write_paths: Optional list of glob patterns that restrict
            which paths can be written to. If None, all paths within cwd
            are writable. Uses gitignore-style glob patterns (via pathspec)
            with root-anchored semantics.

    Pattern Semantics (gitignore-style via pathspec):
        Patterns are anchored to the working directory root and use
        familiar gitignore glob semantics:

        - '*' matches within a single path component
        - '**' matches zero or more directories at any depth
        - '?' matches any single character
        - '[seq]' matches any character in seq

    Examples:
        - 'src/**/*.py' matches 'src/foo.py', 'src/sub/bar.py', 'src/a/b/c.py'
        - 'tests/**' matches everything under tests/ at any depth
        - '*.py' matches only Python files at the root
        - '**/*.py' matches Python files at any depth

    Example:
        resolver = PathResolver(Path("/project"), ["src/**/*.py", "tests/**"])

        # This works - within cwd
        path = resolver.resolve("src/main.py")

        # This raises PathSecurityError - outside cwd
        path = resolver.resolve("../secret.txt")
    """

    def __init__(
        self,
        cwd: Path,
        allowed_write_paths: list[str] | None = None,
    ) -> None:
        self._cwd = cwd.resolve()
        self._allowed_write_paths = allowed_write_paths
        # Pre-compile the pathspec for efficiency
        self._pathspec: pathspec.PathSpec | None = None
        if allowed_write_paths:
            # Anchor patterns to root by prefixing with / if not already anchored
            # In gitignore, patterns without / match anywhere in the tree
            # We want root-anchored behavior by default for security
            anchored_patterns = []
            for pattern in allowed_write_paths:
                if pattern.startswith("/") or pattern.startswith("**/"):
                    # Already anchored or explicitly recursive
                    anchored_patterns.append(pattern)
                else:
                    # Anchor to root
                    anchored_patterns.append("/" + pattern)
            self._pathspec = pathspec.PathSpec.from_lines("gitwildmatch", anchored_patterns)

    @property
    def cwd(self) -> Path:
        """The resolved working directory."""
        return self._cwd

    def resolve(self, path: str) -> Path:
        """Resolve a path relative to cwd, ensuring it stays within cwd.

        Args:
            path: Path to resolve. Can be relative or absolute.

        Returns:
            The resolved absolute path.

        Raises:
            PathSecurityError: If the resolved path is outside the working directory.
        """
        # Handle absolute paths by making them relative to cwd
        path_obj = Path(path)
        resolved = path_obj.resolve() if path_obj.is_absolute() else (self._cwd / path).resolve()

        # Security check: ensure path is within cwd
        try:
            resolved.relative_to(self._cwd)
        except ValueError as e:
            raise PathSecurityError(
                f"Path '{path}' resolves outside working directory",
                path=path,
                cwd=self._cwd,
                reason="directory_traversal",
            ) from e

        return resolved

    def is_write_allowed(self, resolved_path: Path) -> bool:
        """Check if a path matches allowed write patterns.

        Uses gitignore-style glob patterns anchored to the working directory.
        This provides intuitive matching where 'src/**/*.py' matches all
        Python files under src/ at any depth.

        Args:
            resolved_path: An already-resolved absolute path.

        Returns:
            True if writing to this path is allowed, False otherwise.
        """
        # None means no restrictions - allow all
        if self._allowed_write_paths is None:
            return True
        # Empty list means nothing is allowed
        if not self._allowed_write_paths:
            return False

        # Get path relative to cwd and convert to POSIX format for pathspec
        rel_path = str(resolved_path.relative_to(self._cwd))
        # Normalize path separators to forward slashes (pathspec expects POSIX paths)
        rel_path = rel_path.replace("\\", "/")
        # _pathspec is always set when _allowed_write_paths is non-empty (checked above)
        assert self._pathspec is not None
        return self._pathspec.match_file(rel_path)

    def resolve_and_check_write(self, path: str) -> Path:
        """Resolve a path and verify write access in one call.

        Convenience method that combines resolve() and is_write_allowed().

        Args:
            path: Path to resolve and check.

        Returns:
            The resolved absolute path.

        Raises:
            PathSecurityError: If the path is outside cwd or not writable.
        """
        resolved = self.resolve(path)

        if not self.is_write_allowed(resolved):
            raise PathSecurityError(
                f"Write not allowed to '{path}'",
                path=path,
                cwd=self._cwd,
                reason="write_restricted",
            )

        return resolved


class FileOperations:
    """Low-level file operations with path security and modification tracking.

    This class provides the core file I/O primitives that both
    AnthropicTextEditor and FileTools use. It handles:
    - Path resolution and security checks via PathResolver
    - File existence checks
    - Parent directory creation for writes
    - Modification tracking

    All methods return ToolResult. For write operations, the new content
    is stored in result.metadata["new_content"].

    Args:
        resolver: PathResolver instance for secure path handling.

    Example:
        resolver = PathResolver(cwd=Path("/project"))
        ops = FileOperations(resolver)

        result = ops.read_file("src/main.py")
        if result.success:
            print(result.output)

        result = ops.write_file("src/new.py", "print('hello')")
        print(ops.files_modified)  # {"src/new.py": "print('hello')"}
    """

    def __init__(self, resolver: PathResolver) -> None:
        self._resolver = resolver
        self._files_modified: dict[str, str] = {}

    @property
    def cwd(self) -> Path:
        """The working directory."""
        return self._resolver.cwd

    @property
    def files_modified(self) -> dict[str, str]:
        """Files modified since last reset (path -> content)."""
        return self._files_modified.copy()

    def reset(self) -> None:
        """Clear modification tracking."""
        self._files_modified = {}

    def read_file(self, path: str) -> ToolResult:
        """Read file contents.

        Args:
            path: Path relative to cwd.

        Returns:
            ToolResult with content in output, or error.
        """
        try:
            resolved = self._resolver.resolve(path)
        except PathSecurityError as e:
            return ToolResult.from_error(ToolErrorCode.PATH_SECURITY, e.message)

        if not resolved.exists():
            return ToolResult.from_error(ToolErrorCode.FILE_NOT_FOUND, f"File not found: {path}")

        try:
            content = resolved.read_text(encoding="utf-8")
        except OSError as e:
            return ToolResult.from_error(ToolErrorCode.IO_ERROR, f"Failed to read file: {e}")
        except UnicodeDecodeError:
            return ToolResult.from_error(ToolErrorCode.IO_ERROR, f"Cannot read {path}: file is not valid UTF-8 text")

        return ToolResult(output=content, success=True)

    def write_file(
        self,
        path: str,
        content: str,
        *,
        overwrite: bool = True,
    ) -> ToolResult:
        """Write content to a file.

        Args:
            path: Path relative to cwd.
            content: Content to write.
            overwrite: If False, fail if file exists.

        Returns:
            ToolResult with success message. New content in metadata["new_content"].
        """
        try:
            resolved = self._resolver.resolve_and_check_write(path)
        except PathSecurityError as e:
            return ToolResult.from_error(ToolErrorCode.PATH_SECURITY, e.message)

        if not overwrite and resolved.exists():
            return ToolResult.from_error(ToolErrorCode.IO_ERROR, f"File already exists: {path}")

        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content, encoding="utf-8")
        except OSError as e:
            return ToolResult.from_error(ToolErrorCode.IO_ERROR, f"Failed to write file: {e}")

        rel_path = str(resolved.relative_to(self._resolver.cwd))
        self._files_modified[rel_path] = content

        return ToolResult(
            output=f"Wrote {len(content)} bytes to {path}",
            success=True,
            metadata={"new_content": content},
        )

    def replace_string(
        self,
        path: str,
        old_str: str,
        new_str: str,
    ) -> ToolResult:
        """Replace a unique string in a file.

        The old_str must match exactly one location in the file.

        Args:
            path: Path relative to cwd.
            old_str: String to find (must be unique).
            new_str: Replacement string.

        Returns:
            ToolResult with success message. New content in metadata["new_content"].
        """
        # First resolve and check existence
        try:
            resolved = self._resolver.resolve(path)
        except PathSecurityError as e:
            return ToolResult.from_error(ToolErrorCode.PATH_SECURITY, e.message)

        if not resolved.exists():
            return ToolResult.from_error(ToolErrorCode.FILE_NOT_FOUND, f"File not found: {path}")

        # Check write permission
        if not self._resolver.is_write_allowed(resolved):
            return ToolResult.from_error(ToolErrorCode.PATH_SECURITY, f"Cannot edit {path}. Write not allowed.")

        try:
            content = resolved.read_text(encoding="utf-8")
        except OSError as e:
            return ToolResult.from_error(ToolErrorCode.IO_ERROR, f"Failed to read file: {e}")
        except UnicodeDecodeError:
            return ToolResult.from_error(ToolErrorCode.IO_ERROR, f"Cannot edit {path}: file is not valid UTF-8 text")

        # Check uniqueness
        count = content.count(old_str)
        if count == 0:
            return ToolResult.from_error(ToolErrorCode.STRING_NOT_FOUND, "No match found for replacement text.")
        if count > 1:
            return ToolResult.from_error(
                ToolErrorCode.STRING_NOT_FOUND,
                f"Found {count} matches. Provide more context for unique match.",
            )

        new_content = content.replace(old_str, new_str, 1)

        try:
            resolved.write_text(new_content, encoding="utf-8")
        except OSError as e:
            return ToolResult.from_error(ToolErrorCode.IO_ERROR, f"Error writing file: {e}")

        rel_path = str(resolved.relative_to(self._resolver.cwd))
        self._files_modified[rel_path] = new_content

        return ToolResult(
            output="Successfully replaced text.",
            success=True,
            metadata={"new_content": new_content},
        )

    def list_directory(
        self,
        path: str,
        *,
        max_depth: int = 3,
        include_hidden: bool = False,
    ) -> ToolResult:
        """List directory contents.

        Args:
            path: Path relative to cwd.
            max_depth: Maximum recursion depth.
            include_hidden: Include files starting with '.'.

        Returns:
            ToolResult with directory listing or error.
        """
        try:
            resolved = self._resolver.resolve(path)
        except PathSecurityError as e:
            return ToolResult.from_error(ToolErrorCode.PATH_SECURITY, e.message)

        if not resolved.exists():
            return ToolResult.from_error(ToolErrorCode.FILE_NOT_FOUND, f"Directory not found: {path}")

        if not resolved.is_dir():
            return ToolResult.from_error(ToolErrorCode.NOT_A_DIRECTORY, f"Not a directory: {path}")

        listing = self._build_listing(resolved, max_depth, 0, include_hidden)
        output = listing if listing else "(empty directory)"
        return ToolResult(output=output, success=True)

    def _build_listing(
        self,
        dir_path: Path,
        max_depth: int,
        current_depth: int,
        include_hidden: bool,
    ) -> str:
        """Build recursive directory listing."""
        if current_depth > max_depth:
            return ""

        lines: list[str] = []
        indent = "  " * current_depth

        try:
            items = sorted(dir_path.iterdir())
        except OSError:
            return ""

        for item in items:
            if not include_hidden and item.name.startswith("."):
                continue
            if item.is_dir():
                lines.append(f"{indent}{item.name}/")
                if current_depth < max_depth:
                    sublist = self._build_listing(item, max_depth, current_depth + 1, include_hidden)
                    if sublist:
                        lines.append(sublist)
            else:
                lines.append(f"{indent}{item.name}")

        return "\n".join(lines)

    def check_exists(self, path: str) -> ToolResult:
        """Check if a path exists.

        Args:
            path: Path relative to cwd.

        Returns:
            ToolResult with "file", "directory", or "not_found".
        """
        try:
            resolved = self._resolver.resolve(path)
        except PathSecurityError as e:
            return ToolResult.from_error(ToolErrorCode.PATH_SECURITY, e.message)

        if not resolved.exists():
            return ToolResult(output="not_found", success=True)

        if resolved.is_dir():
            return ToolResult(output="directory", success=True)

        return ToolResult(output="file", success=True)

    def is_directory(self, path: str) -> bool:
        """Check if path is a directory.

        Args:
            path: Path relative to cwd.

        Returns:
            True if path is a directory, False otherwise.
        """
        try:
            resolved = self._resolver.resolve(path)
            return resolved.is_dir()
        except PathSecurityError:
            return False


__all__ = ["FileOperations", "PathResolver"]
