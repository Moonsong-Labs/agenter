"""Constants for claude-agent backend.

These constants map to tool names used by claude-agent-sdk.
When claude-agent-sdk updates, these may need to be reviewed.
"""

from typing import Final

# Tool names from claude-agent-sdk that modify files.
# When claude-agent-sdk updates, check these names at:
# https://github.com/anthropics/claude-agent-sdk
#
# These tools create or modify files and should be tracked for
# file modification reporting.
FILE_MODIFICATION_TOOLS: Final[frozenset[str]] = frozenset(
    {
        "Write",  # Creates/overwrites files
        "Edit",  # Edits existing files
        "str_replace_editor",  # Anthropic's built-in text editor
        "create",  # Creates new files
    }
)

# Path input keys used by different tools
# Different tools use different parameter names for file paths
PATH_INPUT_KEYS: Final[tuple[str, ...]] = ("path", "file_path")

# SDK structured output tool (created internally when output_format is set)
# Workaround for Issue #105: SDK doesn't populate message.structured_output
# https://github.com/anthropics/claude-agent-sdk-typescript/issues/105
SDK_STRUCTURED_OUTPUT_TOOL: Final[str] = "StructuredOutput"
SDK_STRUCTURED_OUTPUT_KEY: Final[str] = "parameter"

# MCP server name for refusal tool (Claude-agent specific due to MCP naming)
# The tool schema and instructions are in the shared refusal module
REFUSAL_MCP_SERVER_NAME: Final[str] = "agenter-refusal"
