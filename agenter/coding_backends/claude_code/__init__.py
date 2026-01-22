"""Claude Code backend using claude-agent-sdk.

This backend wraps Claude Code (via claude-agent-sdk) to provide
battle-tested tools and agent loop maintained by Anthropic.

SECURITY MODES
==============
This backend supports two security modes via the `sandbox` parameter:

1. sandbox=True (default): Uses Claude Code's native OS-level sandboxing
2. sandbox=False: No restrictions - files can be read/written anywhere

For strict path sandboxing with allowed_write_paths, use AnthropicSDKBackend.
"""

from .backend import ClaudeCodeBackend

__all__ = ["ClaudeCodeBackend"]
