"""Codex backend for Agenter.

This module provides the CodexBackend which wraps the OpenAI Codex CLI
running as an MCP server.

Example:
    from agenter.backends.codex import CodexBackend, CodexMCPServer

    backend = CodexBackend(
        model="o3",
        approval_policy="never",
        sandbox="workspace-write",
    )
    await backend.connect("/path/to/project")
"""

from .backend import CodexBackend, CodexMCPServer

__all__ = ["CodexBackend", "CodexMCPServer"]
