"""MCP server subprocess for custom tools.

This module is run as a subprocess by CodexBackend to provide custom tools
to the Codex CLI via stdio MCP protocol.

Run as: python -m agenter.backends.codex.mcp_tool_server --tools /path/to/tools.pkl
"""

from __future__ import annotations

import argparse
import asyncio
import sys


def main() -> None:
    """Main entry point for the MCP tool server subprocess."""
    parser = argparse.ArgumentParser(description="MCP server for agenter custom tools")
    parser.add_argument("--tools", required=True, help="Path to cloudpickle'd tools file")
    args = parser.parse_args()

    try:
        import cloudpickle  # type: ignore[import-not-found]
        from mcp.server.fastmcp import FastMCP
    except ImportError as e:
        print(f"Missing dependency: {e}", file=sys.stderr)
        print("Install with: pip install agenter[codex]", file=sys.stderr)
        sys.exit(1)

    # Load serialized tools from pickle file
    try:
        with open(args.tools, "rb") as f:
            tools = cloudpickle.load(f)
    except (OSError, EOFError, ImportError, AttributeError, ModuleNotFoundError) as e:
        # OSError: file access issues
        # EOFError: truncated pickle
        # ImportError/ModuleNotFoundError: missing modules for unpickling
        # AttributeError: class definition changed since pickling
        print(f"Failed to load tools from {args.tools}: {e}", file=sys.stderr)
        sys.exit(1)

    # Create FastMCP server
    server = FastMCP("agenter-tools")

    def run_async_tool(coro):  # type: ignore[no-untyped-def]
        """Run async coroutine, handling both running and non-running event loops."""
        try:
            asyncio.get_running_loop()  # Check if loop exists
        except RuntimeError:
            # No running loop, safe to use asyncio.run()
            return asyncio.run(coro)
        else:
            # Already in a loop (e.g., FastMCP's event loop)
            # Create a new loop in this thread to run the coroutine
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()

    def parse_codex_kwargs(kwargs: dict) -> dict:
        """Parse Codex's kwargs format into actual arguments.

        Codex MCP passes arguments in format: {'kwargs': 'key1=value1, key2=value2'}
        This function parses that string back into a proper dict.
        """
        if "kwargs" in kwargs and isinstance(kwargs["kwargs"], str):
            parsed: dict[str, int | float | bool | str] = {}
            for part in kwargs["kwargs"].split(","):
                part = part.strip()
                if "=" in part:
                    key, value = part.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    # Try to convert to int/float/bool
                    if value.isdigit():
                        parsed[key] = int(value)
                    elif value.replace(".", "", 1).isdigit():
                        parsed[key] = float(value)
                    elif value.lower() in ("true", "false"):
                        parsed[key] = value.lower() == "true"
                    else:
                        parsed[key] = value
            return parsed
        return kwargs

    # Register each tool dynamically using @server.tool() decorator
    for tool in tools:
        # Use decorator with explicit name/description
        # Capture tool in default arg to avoid closure issues
        @server.tool(name=tool.name, description=tool.description)
        def tool_handler(tool=tool, **kwargs):  # type: ignore[no-untyped-def]
            # Parse Codex's kwargs format if needed
            parsed_kwargs = parse_codex_kwargs(kwargs)
            # Run async tool.execute() - handles running event loops
            result = run_async_tool(tool.execute(parsed_kwargs))
            return result.output

    # Run stdio server (blocks until connection closes)
    server.run()


if __name__ == "__main__":
    main()
