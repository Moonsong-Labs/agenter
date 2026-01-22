"""Anthropic built-in text editor tool execution handler.

This implements execution for Anthropic's built-in text_editor_20250728 tool.
Claude is specifically trained on this schema, which can improve tool use performance.

Official docs: https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/text-editor-tool
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from ...data_models import PathSecurityError, ToolError, ToolErrorCode, ToolResult
from ...file_system import FileOperations
from .constants import ANTHROPIC_TEXT_EDITOR_TOOL

if TYPE_CHECKING:
    from pathlib import Path

    from ...file_system import PathResolver

logger = structlog.get_logger(__name__)


# Anthropic built-in text editor tool definition
ANTHROPIC_TEXT_EDITOR: dict = {
    "type": "text_editor_20250728",
    "name": ANTHROPIC_TEXT_EDITOR_TOOL,
}


class AnthropicTextEditor:
    """Execute text_editor_20250728 commands.

    Commands (Claude 4):
        view: View file contents (with line numbers) or directory listing.
        create: Create a new file.
        str_replace: Replace text in file (must match exactly one location).
        insert: Insert text at a specific line number.

    Note: Claude 4 does NOT support undo_edit or delete commands.

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
        """Return files modified by this editor."""
        return self._ops.files_modified

    def reset(self) -> None:
        """Clear the list of modified files."""
        self._ops.reset()

    async def execute(self, inputs: dict) -> ToolResult:
        """Execute a text editor command.

        Args:
            inputs: Command inputs including 'command' and command-specific params.

        Returns:
            ToolResult with the operation outcome.
        """
        command = inputs.get("command")
        if not command:
            return ToolResult(
                output="Error: Missing 'command' parameter",
                success=False,
                error=ToolError(code=ToolErrorCode.INVALID_INPUT, message="Missing 'command' parameter"),
            )

        try:
            match command:
                case "view":
                    return self._view(inputs)
                case "create":
                    return self._create(inputs)
                case "str_replace":
                    return self._str_replace(inputs)
                case "insert":
                    return self._insert(inputs)
                case _:
                    return ToolResult(
                        output=f"Error: Unknown command '{command}'",
                        success=False,
                        error=ToolError(code=ToolErrorCode.UNKNOWN_TOOL, message=command),
                    )
        except PathSecurityError as e:
            return ToolResult(
                output=f"Error: {e.message}",
                success=False,
                error=ToolError(code=ToolErrorCode.PATH_SECURITY, message=e.message),
            )
        except Exception as e:
            logger.error("text_editor_error", command=command, error=str(e))
            return ToolResult(
                output=f"Error: {e}",
                success=False,
                error=ToolError(code=ToolErrorCode.EXECUTION_ERROR, message=str(e)),
            )

    def _view(self, inputs: dict) -> ToolResult:
        """View file contents or directory listing."""
        path = inputs.get("path")
        if not path:
            return ToolResult(
                output="Error: Missing 'path' parameter",
                success=False,
                error=ToolError(code=ToolErrorCode.INVALID_INPUT, message="Missing 'path' parameter"),
            )

        # Check if directory first
        if self._ops.is_directory(path):
            result = self._ops.list_directory(path, include_hidden=False)
            return ToolResult(output=result.output, success=result.success, error=result.error)

        # Read file contents
        result = self._ops.read_file(path)
        if not result.success:
            # Add "Error: " prefix for consistency with original behavior
            output = result.output if result.output.startswith("Error:") else f"Error: {result.output}"
            return ToolResult(output=output, success=False, error=result.error)

        # View-specific: add line numbers and handle view_range
        view_range = inputs.get("view_range")
        lines = result.output.splitlines()

        if view_range:
            start = view_range[0] - 1  # 1-indexed
            end = len(lines) if view_range[1] == -1 else view_range[1]
            lines = lines[start:end]
            start_line = view_range[0]
        else:
            start_line = 1

        numbered = [f"{i + start_line}: {line}" for i, line in enumerate(lines)]
        return ToolResult(output="\n".join(numbered), success=True)

    def _create(self, inputs: dict) -> ToolResult:
        """Create a new file."""
        path = inputs.get("path")
        file_text = inputs.get("file_text", "")

        if not path:
            return ToolResult(
                output="Error: Missing 'path' parameter",
                success=False,
                error=ToolError(code=ToolErrorCode.INVALID_INPUT, message="Missing 'path' parameter"),
            )

        result = self._ops.write_file(path, file_text, overwrite=False)
        if result.success:
            return ToolResult(output=f"Successfully created {path}", success=True)

        # Customize error message for existing file
        if result.error and "already exists" in result.output:
            msg = f"File already exists: {path}. Use str_replace to modify."
            return ToolResult(
                output=f"Error: {msg}",
                success=False,
                error=ToolError(code=ToolErrorCode.IO_ERROR, message=msg),
            )

        return ToolResult(output=result.output, success=False, error=result.error)

    def _str_replace(self, inputs: dict) -> ToolResult:
        """Replace text in a file. Must match exactly one location."""
        path = inputs.get("path")
        old_str = inputs.get("old_str")
        new_str = inputs.get("new_str")

        if not path:
            return ToolResult(
                output="Error: Missing 'path' parameter",
                success=False,
                error=ToolError(code=ToolErrorCode.INVALID_INPUT, message="Missing 'path' parameter"),
            )
        if old_str is None:
            return ToolResult(
                output="Error: Missing 'old_str' parameter",
                success=False,
                error=ToolError(code=ToolErrorCode.INVALID_INPUT, message="Missing 'old_str' parameter"),
            )
        if new_str is None:
            return ToolResult(
                output="Error: Missing 'new_str' parameter",
                success=False,
                error=ToolError(code=ToolErrorCode.INVALID_INPUT, message="Missing 'new_str' parameter"),
            )

        result = self._ops.replace_string(path, old_str, new_str)
        if result.success:
            return ToolResult(
                output="Successfully replaced text at exactly one location.",
                success=True,
            )

        # Customize error messages for this tool's interface
        if result.error:
            if result.error.code == ToolErrorCode.STRING_NOT_FOUND:
                if "No match" in result.output:
                    msg = "No match found for replacement. Please check your text and try again."
                else:
                    # Multiple matches - extract count from message if possible
                    msg = result.output.replace("Error: ", "").replace(
                        "Provide more context for unique match.",
                        "Please provide more context to make a unique match.",
                    )
                return ToolResult(
                    output=f"Error: {msg}",
                    success=False,
                    error=ToolError(code=result.error.code, message=msg),
                )
            if result.error.code == ToolErrorCode.PATH_SECURITY:
                msg = f"Permission denied. Cannot write to {path}."
                return ToolResult(
                    output=f"Error: {msg}",
                    success=False,
                    error=ToolError(code=result.error.code, message=msg),
                )

        return ToolResult(output=result.output, success=False, error=result.error)

    def _insert(self, inputs: dict) -> ToolResult:
        """Insert text at a specific line number."""
        path = inputs.get("path")
        insert_line = inputs.get("insert_line")
        new_str = inputs.get("new_str")

        if not path:
            return ToolResult(
                output="Error: Missing 'path' parameter",
                success=False,
                error=ToolError(code=ToolErrorCode.INVALID_INPUT, message="Missing 'path' parameter"),
            )
        if insert_line is None:
            return ToolResult(
                output="Error: Missing 'insert_line' parameter",
                success=False,
                error=ToolError(code=ToolErrorCode.INVALID_INPUT, message="Missing 'insert_line' parameter"),
            )
        if new_str is None:
            return ToolResult(
                output="Error: Missing 'new_str' parameter",
                success=False,
                error=ToolError(code=ToolErrorCode.INVALID_INPUT, message="Missing 'new_str' parameter"),
            )

        # Read file contents using FileOperations
        read_result = self._ops.read_file(path)
        if not read_result.success:
            output = read_result.output if read_result.output.startswith("Error:") else f"Error: {read_result.output}"
            return ToolResult(output=output, success=False, error=read_result.error)

        # Check write permission
        try:
            resolved = self._resolver.resolve(path)
            if not self._resolver.is_write_allowed(resolved):
                msg = f"Permission denied. Cannot write to {path}."
                return ToolResult(
                    output=f"Error: {msg}",
                    success=False,
                    error=ToolError(code=ToolErrorCode.PATH_SECURITY, message=msg),
                )
        except PathSecurityError as e:
            return ToolResult(
                output=f"Error: {e.message}",
                success=False,
                error=ToolError(code=ToolErrorCode.PATH_SECURITY, message=e.message),
            )

        # Insert-specific logic
        lines = read_result.output.splitlines(keepends=True)

        # insert_line is the line AFTER which to insert (0 = beginning of file)
        idx = max(0, min(insert_line, len(lines)))

        # Ensure new_str ends with newline if inserting mid-file
        insert_text = new_str
        if not insert_text.endswith("\n") and idx < len(lines):
            insert_text += "\n"

        lines.insert(idx, insert_text)
        new_content = "".join(lines)

        # Write using FileOperations
        write_result = self._ops.write_file(path, new_content, overwrite=True)
        if not write_result.success:
            return ToolResult(output=write_result.output, success=False, error=write_result.error)

        return ToolResult(
            output=f"Successfully inserted text after line {insert_line}",
            success=True,
        )
