"""Constants for the Claude backend.

Centralizes magic strings used in Claude API interactions.
"""

from typing import Final

# Stop reasons returned by Claude API
STOP_REASON_MAX_TOKENS: Final = "max_tokens"
STOP_REASON_END_TURN: Final = "end_turn"

# Content block types
BLOCK_TYPE_TEXT: Final = "text"
BLOCK_TYPE_TOOL_USE: Final = "tool_use"

# Bedrock-specific block keys
BEDROCK_TOOL_USE_KEY: Final = "toolUse"
BEDROCK_TEXT_KEY: Final = "text"

# Message roles
ROLE_USER: Final = "user"
ROLE_ASSISTANT: Final = "assistant"

# Tool result keys
TOOL_RESULT_TYPE: Final = "tool_result"
TOOL_RESULT_ERROR_KEY: Final = "is_error"

# Anthropic built-in tools
ANTHROPIC_TEXT_EDITOR_TOOL: Final = "str_replace_based_edit_tool"
