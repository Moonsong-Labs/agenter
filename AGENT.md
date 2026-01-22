# AGENT.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Documentation

This project has comprehensive documentation in the `docs/` folder:
- **[docs/OVERVIEW.md](docs/OVERVIEW.md)** - Business case and value proposition
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - A summary of the SDK's system design, components, data flow, event streams, and other functionality
- **[docs/NAMING_CONVENTIONS.md](docs/NAMING_CONVENTIONS.md)** - Guidelines for coding style and naming patterns

## Key Commands for Builds and Development

```bash
# Install dependencies (with dev tools)
pip install -e ".[dev]"

# Install with specific backends
pip install -e ".[claude-code]"     # Claude Code SDK backend
pip install -e ".[codex]"           # OpenAI Codex backend
pip install -e ".[openhands]"       # OpenHands backend (any model via litellm)
pip install -e ".[langgraph,pydantic-ai]"  # Framework adapters

# Run all tests
pytest

# Run single test file
pytest tests/test_session.py

# Run single test function
pytest tests/test_session.py::test_function_name -v

# Lint and format
ruff check .
ruff format .

# Type check
mypy agenter
```

## Architecture Overview

Agenter is a backend-agnostic SDK for orchestrating autonomous AI coding agents. It solves the "N x M" integration problem between apps and the fragmented agent landscape by providing:
- **Runtime Agnosticism**: Swap between Claude Code, Codex, or OpenHands with simple configs
- **Unified Governance**: Ensure uniform budget limits and safety policies across all backends
- **Validation Loop**: Code is checked (syntax) and retried automatically

### Layered Architecture

```
Consumer Applications (LangGraph/pydantic-ai adapters)
                    │
                    ▼
        AutonomousCodingAgent (Facade)  ← agent.py
                    │
                    ▼
             CodingSession              ← runtime/session.py
        (iteration loop, budget, validation)
                    │
                    ▼
          CodingBackend Protocol        ← backends/protocol.py
    ┌───────────┼───────────────┬───────────────┐
    ▼           ▼               ▼               ▼
Anthropic   ClaudeCode      Codex         OpenHands
SDKBackend  Backend         Backend       Backend
```

### Backend Implementations

| Backend | Location | Wraps | Security (`sandbox=True`) |
|---------|----------|-------|---------------------------|
| AnthropicSDKBackend | `coding_backends/anthropic_sdk/` | anthropic SDK | PathResolver enforces cwd |
| ClaudeCodeBackend | `coding_backends/claude_code/` | claude-code-sdk | Native OS-level sandbox |
| CodexBackend | `coding_backends/codex/` | openai-agents MCP | `workspace-write` mode |
| OpenHandsBackend | `coding_backends/openhands/` | openhands-sdk | No sandbox (`sandbox=False` required) |

### Key Files

- **`agenter/coding_agent.py`**: `AutonomousCodingAgent` - the public facade, main entry point for all users and consumers
- **`agenter/runtime/session.py`**: `CodingSession` - orchestration loop (execute → validate → retry)
- **`agenter/coding_backends/protocol.py`**: `CodingBackend` protocol that all backends implement
- **`agenter/post_validators/`**: Validator protocol and implementations (currently `SyntaxValidator`)
- **`agenter/adapters/`**: Framework adapters that subclass framework-specific base classes:
  - `langgraph.py`: `create_coding_node()` returns `RunnableLambda` for LangSmith tracing
  - `pydantic_ai.py`: `CodingAgent` subclasses `pydantic_ai.Agent` for Logfire tracing

### Data Flow

1. `CodingRequest` → `AutonomousCodingAgent.execute()`
2. Session runs iteration loop (up to `max_iterations`)
3. Backend executes prompt, streams `BackendMessage`s
4. Validators check output (default: `SyntaxValidator`)
5. On validation failure: retry with error context
6. On pass: return `CodingResult` with status `COMPLETED`
7. On budget exceeded: return `CodingResult` with status `BUDGET_EXCEEDED`

## Code Conventions

- Python 3.11+, async/await throughout
- Pydantic v2 for all models
- structlog for logging
- Type hints required (mypy strict mode)
- Ruff for linting/formatting (line length 120)

## Key Types

```python
from agenter import (
    AutonomousCodingAgent,  # Main entry point
    CodingRequest,          # Input: prompt, cwd, allowed_write_paths, output_type
    CodingResult,           # Output: status, files, summary, usage
    CodingStatus,           # COMPLETED, FAILED, BUDGET_EXCEEDED, REFUSED
    Budget,                 # max_tokens, max_cost_usd, max_iterations
    tool,                   # Decorator for custom tools
)
```

## Backend-specific Notes

### Codex Backend Tool Limitations

Tools run in a subprocess via MCP and are serialized using `cloudpickle`. Tools that capture unpicklable state will fail silently.

**Do:**
- Use module-level functions (not lambdas or closures)
- Import dependencies inside the function
- Pass dynamic state via environment variables or temp files

**Don't:**
- Capture `self` or instance variables in closures
- Capture async clients, locks, or trace recorders
- Use lambda functions that capture outer scope

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#codex-backend-tool-limitations) for examples.
