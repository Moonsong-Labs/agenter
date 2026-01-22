"""Built-in file tools for the Claude backend.

These tools provide basic file operations (read, write, edit, list) that
Claude can use to interact with the file system.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...data_models import PathSecurityError, ToolError, ToolErrorCode, ToolResult
from ...file_system import FileOperations

# Constants for error message preview lengths
STRING_PREVIEW_LONG = 50  # For "not found" error messages
STRING_PREVIEW_SHORT = 30  # For "multiple matches" error messages

if TYPE_CHECKING:
    from pathlib import Path

    from ...file_system import PathResolver


# Tool definitions in Anthropic format
FILE_TOOLS: list[dict] = [
    {
        "name": "read_file",
        "description": "Read the contents of a file at the given path.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to read (relative to cwd)"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file, creating it if it doesn't exist.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to write (relative to cwd)"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "Replace a specific string in a file with new content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to edit (relative to cwd)"},
                "old_string": {"type": "string", "description": "String to find"},
                "new_string": {"type": "string", "description": "Replacement string"},
            },
            "required": ["path", "old_string", "new_string"],
        },
    },
    {
        "name": "list_files",
        "description": "List files in a directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to list (relative to cwd)"},
            },
        },
    },
]


class FileTools:
    """Executor for built-in file tools.

    This class handles the execution of read_file, write_file, edit_file,
    and list_files tools using FileOperations for the core logic.

    Args:
        path_resolver: PathResolver instance for secure path handling.
    """

    def __init__(self, path_resolver: PathResolver) -> None:
        self._resolver = path_resolver
        self._ops = FileOperations(path_resolver)

    @property
    def cwd(self) -> Path:
        """The working directory."""
        return self._ops.cwd

    def modified_files(self) -> dict[str, str]:
        """Return files modified by these tools."""
        return self._ops.files_modified

    def reset(self) -> None:
        """Clear the list of modified files."""
        self._ops.reset()

    async def execute(self, name: str, inputs: dict) -> ToolResult:
        """Execute a file tool by name.

        Args:
            name: Tool name (read_file, write_file, edit_file, list_files).
            inputs: Tool inputs dictionary.

        Returns:
            ToolResult with the operation outcome.
        """
        try:
            match name:
                case "read_file":
                    return self._read_file(inputs["path"])
                case "write_file":
                    return self._write_file(inputs["path"], inputs["content"])
                case "edit_file":
                    return self._edit_file(
                        inputs["path"],
                        inputs["old_string"],
                        inputs["new_string"],
                    )
                case "list_files":
                    return self._list_files(inputs.get("path", "."))
                case _:
                    return ToolResult(
                        output=f"Error: Unknown tool: {name}",
                        success=False,
                        error=ToolError(code=ToolErrorCode.UNKNOWN_TOOL, message=name),
                    )
        except KeyError as e:
            received = list(inputs.keys())
            msg = f"Missing required parameter {e}. You sent: {received}."
            return ToolResult(
                output=f"Error: {msg}",
                success=False,
                error=ToolError(code=ToolErrorCode.INVALID_INPUT, message=msg),
            )
        except PathSecurityError as e:
            return ToolResult(
                output=f"Error: {e.message}",
                success=False,
                error=ToolError(code=ToolErrorCode.PATH_SECURITY, message=e.message),
            )
        except OSError as e:
            return ToolResult(
                output=f"Error: File system error: {e}",
                success=False,
                error=ToolError(code=ToolErrorCode.IO_ERROR, message=str(e)),
            )

    def _read_file(self, path: str) -> ToolResult:
        """Read file contents."""
        result = self._ops.read_file(path)
        return ToolResult(output=result.output, success=result.success, error=result.error)

    def _write_file(self, path: str, content: str) -> ToolResult:
        """Write content to a file."""
        result = self._ops.write_file(path, content, overwrite=True)
        return ToolResult(output=result.output, success=result.success, error=result.error)

    def _edit_file(self, path: str, old_string: str, new_string: str) -> ToolResult:
        """Edit a file by replacing a string."""
        result = self._ops.replace_string(path, old_string, new_string)
        if result.success:
            return ToolResult(output=f"Edited {path}", success=True)

        # Customize error messages for this tool's interface
        if result.error and result.error.code == ToolErrorCode.STRING_NOT_FOUND:
            if "No match" in result.output:
                preview = (
                    old_string[:STRING_PREVIEW_LONG] + "..." if len(old_string) > STRING_PREVIEW_LONG else old_string
                )
                return ToolResult(
                    output=f"String not found in {path}: '{preview}'",
                    success=False,
                    error=ToolError(code=ToolErrorCode.STRING_NOT_FOUND, message=path),
                )
            else:
                # Multiple matches - read file to get count for message
                read_result = self._ops.read_file(path)
                if read_result.success:
                    match_count = read_result.output.count(old_string)
                    preview = (
                        old_string[:STRING_PREVIEW_SHORT] + "..."
                        if len(old_string) > STRING_PREVIEW_SHORT
                        else old_string
                    )
                    return ToolResult(
                        output=(
                            f"Ambiguous edit: '{preview}' found {match_count} times in {path}. "
                            "Provide more surrounding context to make the match unique."
                        ),
                        success=False,
                        error=ToolError(
                            code=ToolErrorCode.STRING_NOT_FOUND,
                            message=f"Multiple matches ({match_count}) in {path}",
                        ),
                    )

        return ToolResult(output=result.output, success=False, error=result.error)

    def _list_files(self, path: str) -> ToolResult:
        """List files in a directory.

        Note: This method uses a flat "d/f prefix" format different from
        FileOperations.list_directory which uses recursive indented output.
        """
        # Use FileOperations for existence/type checking but custom formatting
        check_result = self._ops.check_exists(path)
        if not check_result.success:
            return ToolResult(output=check_result.output, success=False, error=check_result.error)

        if check_result.output == "not_found":
            return ToolResult(
                output=f"Error: Directory not found: {path}",
                success=False,
                error=ToolError(code=ToolErrorCode.FILE_NOT_FOUND, message=path),
            )

        if check_result.output != "directory":
            return ToolResult(
                output=f"Error: Not a directory: {path}",
                success=False,
                error=ToolError(code=ToolErrorCode.NOT_A_DIRECTORY, message=path),
            )

        # Custom flat format with d/f prefixes
        try:
            resolved = self._resolver.resolve(path)
            files = [("d " if item.is_dir() else "f ") + item.name for item in sorted(resolved.iterdir())]
            output = "\n".join(files) if files else "(empty directory)"
            return ToolResult(output=output, success=True)
        except PathSecurityError as e:
            return ToolResult(
                output=f"Error: {e.message}",
                success=False,
                error=ToolError(code=ToolErrorCode.PATH_SECURITY, message=e.message),
            )
