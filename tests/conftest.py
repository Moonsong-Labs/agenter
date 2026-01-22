"""Pytest configuration and fixtures.

This file runs before any test module imports, ensuring clean environment.
"""

import contextlib
import logging
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Clear conflicting env vars BEFORE any SDK imports (mirrors .envrc)
# These may be set by the parent shell (e.g., Claude Code session)
for var in [
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BEDROCK_BASE_URL",
    "CLAUDE_CODE_USE_BEDROCK",
    # AWS vars that might be set by Claude Code
    "AWS_BEARER_TOKEN_BEDROCK",
    "AWS_REGION",
]:
    os.environ.pop(var, None)

# Load project's .env file (override=True to replace any remaining vars).
#
# - Developers often keep local API keys in `.env` for integration tests.
# - CI and sandboxed runners may want to avoid/skip loading it.
# - Some sandboxed runners may also block access to gitignored files like `.env`.
if not os.environ.get("AGENTER_SKIP_DOTENV"):
    dotenv_path = Path(__file__).parent.parent / ".env"
    # Treat unreadable `.env` the same as a missing `.env`.
    with contextlib.suppress(OSError):
        load_dotenv(dotenv_path, override=True)


# =============================================================================
# Suppress asyncio cleanup errors from MCP/anyio
# =============================================================================
# When running MCP-based backends (codex) in pytest-asyncio, the MCP library's
# async generators may not clean up properly, causing RuntimeError during
# garbage collection. These errors don't affect test correctness - they're
# just cleanup order issues between anyio and pytest-asyncio.


@pytest.fixture(autouse=True)
def suppress_asyncio_cleanup_errors(caplog):
    """Suppress asyncio cleanup errors that don't affect test correctness."""
    # Set asyncio logger to only show CRITICAL during tests
    asyncio_logger = logging.getLogger("asyncio")
    original_level = asyncio_logger.level
    asyncio_logger.setLevel(logging.CRITICAL)

    yield

    # Restore original level
    asyncio_logger.setLevel(original_level)
