#!/usr/bin/env python3
"""Manual integration test for ClaudeCodeBackend.

This test cannot run in pytest due to subprocess/environment conflicts.
Run directly with: python tests/manual/test_claude_agent.py

Requirements:
- ANTHROPIC_API_KEY environment variable set
- claude CLI installed (npm install -g @anthropic/claude-code)
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path


def check_requirements() -> bool:
    """Check if required environment is set up."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set")
        return False

    import shutil

    if not shutil.which("claude"):
        print("ERROR: claude CLI not found")
        return False

    return True


async def test_file_creation():
    """Test that ClaudeCodeBackend can create files."""
    from agenter.coding_backends.claude_code import ClaudeCodeBackend

    print("\n=== Test: File Creation ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = ClaudeCodeBackend(sandbox=False)
        await backend.connect(tmpdir)

        print(f"Working directory: {tmpdir}")
        print("Executing: Create hello.py with: print('hello')")

        async for msg in backend.execute("Create hello.py with: print('hello')"):
            print(f"  {type(msg).__name__}: {str(msg)[:80]}")

        py_path = Path(tmpdir) / "hello.py"
        if py_path.exists():
            print(f"✓ File created: {py_path}")
            print(f"  Content: {py_path.read_text()}")
            await backend.disconnect()
            return True
        else:
            print("✗ File not created")
            await backend.disconnect()
            return False


async def test_custom_tools():
    """Test that ClaudeCodeBackend can use custom tools."""
    from agenter import ToolResult, tool
    from agenter.coding_backends.claude_code import ClaudeCodeBackend
    from agenter.data_models import ToolCallMessage

    print("\n=== Test: Custom Tools ===")

    @tool("get_magic_number", "Returns 42 multiplied by the given multiplier", {"multiplier": int})
    async def get_magic_number(args: dict) -> ToolResult:
        multiplier = args.get("multiplier", 1)
        return ToolResult(output=str(42 * multiplier), success=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        backend = ClaudeCodeBackend(sandbox=False, extra_tools=[get_magic_number])
        await backend.connect(tmpdir)

        print(f"Working directory: {tmpdir}")
        print("Executing: Use the get_magic_number tool with multiplier=3")

        messages = []
        async for msg in backend.execute("Use the get_magic_number tool with multiplier=3 and tell me the result."):
            messages.append(msg)
            print(f"  {type(msg).__name__}: {str(msg)[:80]}")

        tool_calls = [m for m in messages if isinstance(m, ToolCallMessage)]
        # Tool may be called as "get_magic_number" or "mcp__agenter-tools__get_magic_number"
        magic_calls = [t for t in tool_calls if "get_magic_number" in t.tool_name]

        if magic_calls:
            print("✓ Custom tool was called")
            await backend.disconnect()
            return True
        else:
            print("✗ Custom tool was not called")
            await backend.disconnect()
            return False


async def test_sandbox_modes():
    """Test sandbox=True and sandbox=False modes."""
    from agenter.coding_backends.claude_code import ClaudeCodeBackend

    print("\n=== Test: Sandbox Modes ===")

    # Test sandbox=True
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = ClaudeCodeBackend(sandbox=True)
        await backend.connect(tmpdir)
        print("✓ sandbox=True works")
        await backend.disconnect()

    # Test sandbox=False
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = ClaudeCodeBackend(sandbox=False)
        await backend.connect(tmpdir)
        print("✓ sandbox=False works")
        await backend.disconnect()

    return True


async def main():
    """Run all manual tests."""
    print("=" * 60)
    print("ClaudeCodeBackend Manual Integration Tests")
    print("=" * 60)

    if not check_requirements():
        sys.exit(1)

    results = []

    try:
        results.append(("File Creation", await test_file_creation()))
    except Exception as e:
        print(f"✗ File Creation failed: {e}")
        results.append(("File Creation", False))

    try:
        results.append(("Custom Tools", await test_custom_tools()))
    except Exception as e:
        print(f"✗ Custom Tools failed: {e}")
        results.append(("Custom Tools", False))

    try:
        results.append(("Sandbox Modes", await test_sandbox_modes()))
    except Exception as e:
        print(f"✗ Sandbox Modes failed: {e}")
        results.append(("Sandbox Modes", False))

    # Summary
    print("\n" + "=" * 60)
    print("Results:")
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {name}")

    all_passed = all(passed for _, passed in results)
    print("=" * 60)
    print(f"Overall: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
