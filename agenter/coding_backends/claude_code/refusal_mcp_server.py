"""MCP server subprocess for Refusal tool.

This module is run as a subprocess by ClaudeCodeBackend to provide the Refusal tool
to Claude Code via stdio MCP protocol.

Run as: python -m agenter.coding_backends.claude_code.refusal_mcp_server
"""

from __future__ import annotations

import sys


def main() -> None:
    """Main entry point for the refusal MCP server subprocess."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as e:
        print(f"Missing dependency: {e}", file=sys.stderr)
        print("Install mcp: pip install mcp", file=sys.stderr)
        sys.exit(1)

    # Create FastMCP server
    server = FastMCP("agenter-refusal")

    @server.tool()
    def Refusal(reason: str, category: str = "safety") -> str:
        """Signal that you cannot complete the request due to safety, policy, or capability limitations.

        Use this instead of silently failing or returning incomplete results.

        Args:
            reason: Clear explanation of why you cannot proceed with this request
            category: Type of limitation - one of "safety", "policy", or "capability"

        Returns:
            Acknowledgment that the refusal was recorded
        """
        # The actual handling is done by intercepting the tool call in the backend
        # This just returns a confirmation message
        return f"Refusal recorded: {reason} (category: {category})"

    # Run stdio server (blocks until connection closes)
    server.run()


if __name__ == "__main__":
    main()
