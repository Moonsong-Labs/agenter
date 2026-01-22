"""Tracer for recording agent interactions.

Provides a protocol for tracing LLM interactions and a default FileTracer
implementation that saves to timestamped files (like APE's trace_recorder).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Tracer(Protocol):
    """Protocol for tracing agent interactions.

    Implement this protocol to create custom tracers that integrate
    with external logging systems, databases, or observability platforms.

    Example:
        class MyTracer:
            def trace_prompt(self, agent: str, system_prompt: str, user_prompt: str) -> None:
                send_to_logging_service({"type": "prompt", "agent": agent, ...})

        agent = AutonomousCodingAgent(tracer=MyTracer())
    """

    @property
    def output_dir(self) -> Path | None:
        """Directory where traces are saved, if applicable."""
        ...

    def trace_prompt(self, agent: str, system_prompt: str, user_prompt: str) -> None:
        """Record a prompt sent to the LLM."""
        ...

    def trace_response(self, agent: str, content: str) -> None:
        """Record a response from the LLM."""
        ...

    def log_tool_call(self, agent: str, tool_name: str, args: dict[str, Any]) -> None:
        """Record a tool call."""
        ...

    def log_tool_result(self, agent: str, tool_name: str, result: str, success: bool) -> None:
        """Record a tool result."""
        ...


class FileTracer:
    """Default tracer that saves interactions to timestamped files.

    Creates a directory structure like:
        logs/agenter_20251231_120000/
            001_prompt.txt
            001_response.txt
            001_tool_read_file.txt
            002_prompt.txt
            ...

    Example:
        # Auto-create timestamped directory
        tracer = FileTracer()

        # Use specific directory
        tracer = FileTracer("./my_traces")

        # Pass to agent
        agent = AutonomousCodingAgent(tracer=tracer)
        result = await agent.execute(request)
        print(f"Traces saved to: {tracer.output_dir}")
    """

    def __init__(self, output_dir: Path | str | None = None) -> None:
        """Initialize the file tracer.

        Args:
            output_dir: Directory for trace files. If None, creates a
                timestamped directory under ./logs/
        """
        if output_dir:
            self._output_dir = Path(output_dir)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._output_dir = Path(f"./logs/agenter_{timestamp}")

        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._counter = 0
        self._tool_counter = 0

    @property
    def output_dir(self) -> Path:
        """Directory where traces are saved."""
        return self._output_dir

    def trace_prompt(self, agent: str, system_prompt: str, user_prompt: str) -> None:
        """Record a prompt sent to the LLM."""
        self._counter += 1
        self._tool_counter = 0  # Reset tool counter for new prompt

        content = f"Agent: {agent}\n\n"
        if system_prompt:
            content += f"=== SYSTEM PROMPT ===\n\n{system_prompt}\n\n"
        content += f"=== USER PROMPT ===\n\n{user_prompt}"

        self._save(f"{self._counter:03d}_prompt.txt", content)

    def trace_response(self, agent: str, content: str) -> None:
        """Record a response from the LLM."""
        full_content = f"Agent: {agent}\n\n=== RESPONSE ===\n\n{content}"
        self._save(f"{self._counter:03d}_response.txt", full_content)

    def log_tool_call(self, agent: str, tool_name: str, args: dict[str, Any]) -> None:
        """Record a tool call."""
        self._tool_counter += 1
        content = f"Agent: {agent}\nTool: {tool_name}\n\n=== ARGUMENTS ===\n\n{json.dumps(args, indent=2, default=str)}"
        self._save(f"{self._counter:03d}_tool_{self._tool_counter:02d}_{tool_name}.txt", content)

    def log_tool_result(self, agent: str, tool_name: str, result: str, success: bool) -> None:
        """Record a tool result (appends to existing tool file)."""
        # Find the most recent tool file for this tool
        filename = f"{self._counter:03d}_tool_{self._tool_counter:02d}_{tool_name}.txt"
        path = self._output_dir / filename

        status = "SUCCESS" if success else "FAILED"
        append_content = f"\n\n=== RESULT ({status}) ===\n\n{result}"

        if path.exists():
            with path.open("a", encoding="utf-8") as f:
                f.write(append_content)
        else:
            # Create new file if tool call wasn't logged
            content = f"Agent: {agent}\nTool: {tool_name}\n{append_content}"
            self._save(filename, content)

    def _save(self, filename: str, content: str) -> Path:
        """Save content to a file."""
        path = self._output_dir / filename
        path.write_text(content, encoding="utf-8")
        return path


__all__ = ["FileTracer", "Tracer"]
