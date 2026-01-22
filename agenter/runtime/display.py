"""Console display for verbose mode.

Provides rich terminal output and optional file logging for debugging.
"""

import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..data_models import Verbosity

# Display limits for console output truncation
LIMIT_PREVIEW = 500
LIMIT_ARG_VALUE = 100
LIMIT_TOOL_RESULT = 200
LIMIT_TOOL_RESULT_LINES = 3
LIMIT_ERRORS = 5
LIMIT_FILES = 5


class ConsoleDisplay:
    """Rich console output for verbose mode.

    Features:
    - Beautiful colored terminal output using Rich
    - Tool call visualization with arguments
    - LLM prompt/response display (truncated)
    - Execution summary with timing and token usage
    - Optional file logging for full prompts/responses
    """

    def __init__(self, verbosity: Verbosity = Verbosity.NORMAL, output_dir: Path | None = None):
        """Initialize the display.

        Args:
            verbosity: Output verbosity level (QUIET, NORMAL, or VERBOSE)
            output_dir: Optional path to save full prompts/responses
        """
        self.verbosity = verbosity
        self.console = Console() if verbosity != Verbosity.QUIET else None
        self.output_dir = output_dir
        self._message_counter = 0
        self._tool_counter = 0
        self._start_time = time.monotonic()  # Use monotonic for accurate duration
        self._pending_tool: str | None = None  # For combining tool call + result
        self._pending_tool_path: str | None = None  # Path argument for display
        self._pending_tool_file: Path | None = None  # Saved tool JSON file

        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)

    def _print(self, *args: object, **kwargs: Any) -> None:
        """Print only if not quiet."""
        if self.verbosity != Verbosity.QUIET and self.console:
            self.console.print(*args, **kwargs)

    def _save_to_file(self, filename: str, content: str) -> Path | None:
        """Save content to file if output_dir is set."""
        if not self.output_dir:
            return None
        file_path = self.output_dir / filename
        file_path.write_text(content, encoding="utf-8")
        return file_path

    def _make_file_link(self, path: Path) -> str:
        """Create a clickable terminal link to a file."""
        abs_path = path.resolve()
        encoded_path = quote(str(abs_path), safe="/")
        return f"[link=file://{encoded_path}]{abs_path}[/link]"

    def start_session(self, cwd: str, model: str) -> None:
        """Display session start banner."""
        self._print()
        self._print(
            Panel(
                f"[bold]Working directory:[/bold] {cwd}\n[bold]Model:[/bold] {model}",
                title="[bold cyan]Agenter[/bold cyan]",
                border_style="cyan",
                box=box.DOUBLE,
            )
        )
        self._print()

        if self.output_dir:
            self._print(f"[dim]📁 Logs: {self._make_file_link(self.output_dir)}[/dim]")
            self._print()

    def start_iteration(self, iteration: int) -> None:
        """Display iteration start."""
        self._print(f"\n[bold blue]▶ Iteration {iteration}[/bold blue]")

    def display_prompt(self, prompt: str, system_prompt: str | None = None) -> None:
        """Display the prompt being sent to the LLM."""
        self._message_counter += 1
        counter = f"{self._message_counter:03d}"

        full_content = ""
        if system_prompt:
            full_content += "=== SYSTEM PROMPT ===\n\n"
            full_content += system_prompt
            full_content += "\n\n=== USER PROMPT ===\n\n"
        full_content += prompt

        file_path = self._save_to_file(f"{counter}_prompt.txt", full_content)

        if self.verbosity == Verbosity.VERBOSE:
            preview = prompt[:LIMIT_PREVIEW]
            if len(prompt) > LIMIT_PREVIEW:
                preview += "..."

            content = preview
            if file_path:
                content += f"\n\n[dim]📎 Full prompt: {self._make_file_link(file_path)}[/dim]"

            self._print(
                Panel(
                    content,
                    title=f"[cyan]📝 Prompt ({len(full_content):,} chars)[/cyan]",
                    border_style="cyan",
                    box=box.ROUNDED,
                )
            )
        elif self.verbosity == Verbosity.NORMAL:
            # Truncated preview (more than first line, less than VERBOSE)
            preview = prompt[:LIMIT_PREVIEW]
            if len(prompt) > LIMIT_PREVIEW:
                preview += f"\n... [dim]({len(prompt):,} chars total)[/dim]"

            content = preview
            if file_path:
                content += f"\n\n[dim]📎 {self._make_file_link(file_path)}[/dim]"

            self._print(
                Panel(
                    content,
                    title="[cyan]📝 Prompt[/cyan]",
                    border_style="dim cyan",
                    box=box.ROUNDED,
                )
            )

    def display_response(self, response: str, tokens: int) -> None:
        """Display the LLM response."""
        counter = f"{self._message_counter:03d}"

        file_path = self._save_to_file(f"{counter}_response.txt", response)

        if self.verbosity == Verbosity.VERBOSE:
            preview = response[:LIMIT_PREVIEW]
            if len(response) > LIMIT_PREVIEW:
                preview += "..."

            content = preview
            if file_path:
                content += f"\n\n[dim]📎 Full response: {self._make_file_link(file_path)}[/dim]"

            self._print(
                Panel(
                    content,
                    title=f"[green]📨 Response ({len(response):,} chars, {tokens:,} tokens)[/green]",
                    border_style="green",
                    box=box.ROUNDED,
                )
            )
        elif self.verbosity == Verbosity.NORMAL:
            # Truncated preview (more than first line, less than VERBOSE)
            preview = response[:LIMIT_PREVIEW]
            if len(response) > LIMIT_PREVIEW:
                preview += f"\n... [dim]({len(response):,} chars total)[/dim]"

            content = preview
            if file_path:
                content += f"\n\n[dim]📎 {self._make_file_link(file_path)}[/dim]"

            self._print(
                Panel(
                    content,
                    title=f"[green]📨 Response ({tokens:,} tokens)[/green]",
                    border_style="dim green",
                    box=box.ROUNDED,
                )
            )

    def report_tool_call(self, tool_name: str, args: dict[str, Any]) -> None:
        """Display a tool call with its arguments using Rich Panel."""
        self._tool_counter += 1

        # Save full tool data to JSON file
        tool_file: Path | None = None
        if self.output_dir:
            tool_file = self.output_dir / f"{self._tool_counter:03d}_{tool_name}_tool.json"
            tool_data = {"tool": tool_name, "args": args}
            tool_file.write_text(json.dumps(tool_data, indent=2, default=str), encoding="utf-8")

        # Build truncated args preview
        args_preview = []
        for key, value in args.items():
            val_str = str(value)
            if len(val_str) > LIMIT_ARG_VALUE:
                val_str = val_str[:LIMIT_ARG_VALUE] + "..."
            args_preview.append(f"[dim]{key}=[/dim]{val_str}")

        preview_text = f"[bold]{tool_name}[/bold]({', '.join(args_preview)})"
        if tool_file:
            preview_text += f"\n\n[dim]📎 {self._make_file_link(tool_file)}[/dim]"

        if self.verbosity == Verbosity.VERBOSE:
            self._print(
                Panel(
                    preview_text,
                    title="[yellow]🔧 Tool Call[/yellow]",
                    border_style="yellow",
                    box=box.ROUNDED,
                )
            )
        elif self.verbosity == Verbosity.NORMAL:
            # Store for combining with result in panel
            self._pending_tool = tool_name
            self._pending_tool_path = args.get("path", args.get("file_path", ""))
            self._pending_tool_file = tool_file

    def report_tool_result(self, tool_name: str, result: str, success: bool = True) -> None:
        """Display tool result in Rich Panel."""
        display_name = self._pending_tool or tool_name
        path = self._pending_tool_path or ""
        tool_file = self._pending_tool_file

        if self.verbosity == Verbosity.VERBOSE:
            # Show result preview after the tool call panel
            preview = result[:LIMIT_TOOL_RESULT]
            if len(result) > LIMIT_TOOL_RESULT:
                preview += "..."
            lines = preview.split("\n")

            if len(lines) > 1:
                self._print(f"  [magenta]↳ {display_name} returned:[/magenta]")
                for line in lines[:LIMIT_TOOL_RESULT_LINES]:
                    self._print(f"    [dim]{line}[/dim]")
                if len(lines) > LIMIT_TOOL_RESULT_LINES:
                    self._print(f"    [dim]... ({len(lines) - LIMIT_TOOL_RESULT_LINES} more lines)[/dim]")
            else:
                self._print(f"  [magenta]↳[/magenta] {preview}")

        elif self.verbosity == Verbosity.NORMAL:
            # Build compact panel content
            status_icon = "[green]✓[/green]" if success else "[red]✗[/red]"
            border_style = "dim yellow" if success else "red"

            # Build content: tool name with path
            content = f"[bold]{display_name}[/bold] [dim]{path}[/dim]" if path else f"[bold]{display_name}[/bold]"

            # Add file link if available
            if tool_file:
                content += f"\n[dim]📎 {self._make_file_link(tool_file)}[/dim]"

            # Add error details on failure
            if not success:
                error_preview = result[:LIMIT_ARG_VALUE]
                if len(result) > LIMIT_ARG_VALUE:
                    error_preview += "..."
                content += f"\n[red]{error_preview}[/red]"

            self._print(
                Panel(
                    content,
                    title=f"[yellow]🔧 Tool[/yellow] {status_icon}",
                    border_style=border_style,
                    box=box.ROUNDED,
                    padding=(0, 1),
                )
            )

        self._pending_tool = None
        self._pending_tool_path = None
        self._pending_tool_file = None

    def report_validation(self, passed: bool, errors: list[str]) -> None:
        """Display validation result in Rich Panel."""
        if passed:
            self._print(
                Panel(
                    "[green]All checks passed[/green]",
                    title="[green]✓ Validation[/green]",
                    border_style="dim green",
                    box=box.ROUNDED,
                    padding=(0, 1),
                )
            )
        else:
            error_lines = []
            for error in errors[:LIMIT_ERRORS]:
                error_lines.append(f"[red]• {error}[/red]")
            if len(errors) > LIMIT_ERRORS:
                error_lines.append(f"[dim]... and {len(errors) - LIMIT_ERRORS} more errors[/dim]")

            self._print(
                Panel(
                    "\n".join(error_lines),
                    title="[red]✗ Validation Failed[/red]",
                    border_style="red",
                    box=box.ROUNDED,
                    padding=(0, 1),
                )
            )

    def display_summary(
        self,
        success: bool,
        iterations: int,
        tokens: int,
        files: dict[str, str],
    ) -> None:
        """Display execution summary."""
        duration = time.monotonic() - self._start_time

        self._print()
        self._print(
            Panel(
                self._build_summary_table(success, iterations, tokens, duration, files),
                title="[bold]Summary[/bold]",
                border_style="blue",
                box=box.DOUBLE,
            )
        )

    def _build_summary_table(
        self,
        success: bool,
        iterations: int,
        tokens: int,
        duration: float,
        files: dict[str, str],
    ) -> Table:
        """Build the summary table."""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style="bold")
        table.add_column()

        status_icon = "✅" if success else "❌"
        status_text = "Completed" if success else "Failed"
        table.add_row("Status:", f"{status_icon} {status_text}")
        table.add_row("Iterations:", str(iterations))
        table.add_row("Tokens:", f"{tokens:,}")
        table.add_row("Duration:", f"{duration:.1f}s")
        table.add_row("Files modified:", str(len(files)))

        if files and len(files) <= LIMIT_FILES:
            for path in files:
                table.add_row("", f"  [dim]• {path}[/dim]")
        elif files:
            for path in list(files.keys())[:LIMIT_FILES]:
                table.add_row("", f"  [dim]• {path}[/dim]")
            table.add_row("", f"  [dim]... and {len(files) - LIMIT_FILES} more[/dim]")

        return table
