"""Constants for OpenHands backend.

These constants map to tool names and event types used by openhands-sdk.
When openhands-sdk updates, these may need to be reviewed.
"""

from typing import Final

# Default model in litellm format (OpenHands uses litellm for model routing)
DEFAULT_MODEL_OPENHANDS: Final[str] = "openai/gpt-4o"

# Tool names from OpenHands SDK that modify files.
# When openhands-sdk updates, check these names at:
# https://github.com/All-Hands-AI/OpenHands
#
# These tools create or modify files and should be tracked for
# file modification reporting.
FILE_MODIFICATION_TOOLS: Final[frozenset[str]] = frozenset(
    {
        "str_replace_editor",  # OpenHands' file editor tool
        "file_editor",  # Alternative name
        "create_file",  # Creates new files
        "write_file",  # Writes to files
    }
)

# Path input keys used by different tools
# Different tools use different parameter names for file paths
PATH_INPUT_KEYS: Final[tuple[str, ...]] = ("path", "file_path", "filename")

# Event types from OpenHands SDK
EVENT_TYPE_MESSAGE: Final[str] = "message"
EVENT_TYPE_TOOL_CALL: Final[str] = "tool_call"
EVENT_TYPE_TOOL_RESULT: Final[str] = "tool_result"
EVENT_TYPE_FINISH: Final[str] = "finish"
