# Agenter

A backend-agnostic Python SDK for orchestrating autonomous coding agents. Decode your intent into working code and maintain freedom from vendor lock-in.

## TL;DR

- The **_What_**: Single unified integration for AI coding agents,
- The **_Why_**: Avoid duplicating work, consistent safeguards, customer flexibility, **open source potential**,
- **Cost**: One integration step instead of three separate ones.
- **Timeline**: Phase 1 delivers Claude backend with LangGraph adapter.
- **If we don't have this**: Each project builds its own integration → 3x maintenance, inconsistent quality, and lack of uniformity.


## What Are We Building?

A unified SDK that wraps multiple AI coding agents (such as Claude Code, OpenAI Codex, OpenHands, or OpenCode) with:

1. **One universal interface** — Switch backends via configuration, no code changes.
2. **Validation loop** — Code is checked (syntax validation) and retried automatically.
3. **Budget controls** — Hard stops on tokens, cost, and time limits.
4. **Framework adapters** — Drop-in for LangGraph and pydantic-ai.

## Why Does This Matter?

**For LangGraph users**: Autonomous coding step completes without human interrupts.

**For pydantic-ai users**: Same coding capability with backend flexibility.

**For Engineering**: Build once, avoid vendor lock-in, and evaluate alternatives as the AI landscape evolves.

**For Open Source**: Community visibility; external contributions; recruitment support; thought leadership and evangelisation; clean API; Apache-2.0 license; useful beyond Moonsong Labs.

**Team**: learning by doing, and skills development.

## Risks If We Don't Do This

1. **Duplicated effort** — Each project builds its own coding agent integration.
2. **Runaway costs** — No consistent budget controls across projects.
3. **Vendor lock-in** — Can't easily switch backends when customer requirements change.
4. **Quality issues** — Lack of a built-in validation loop means that bad code can ship to customers.
5. **Maintenance burden** — Three separate integrations to maintain and debug.

## Implementation Phases

**Phase 1 (v0)**: Claude backend with validation loop; pydantic-ai and LangGraph adapters.

**Phase 2**: Add Codex and OpenHands backends as customer requirements emerge.

**Phase 3**: Community extensions (additional validators, adapters, backends).


## Project Metadata

| Field | Value |
|-------|-------|
| Package | `agenter` |
| Python | 3.12+ |
| Open Source | Yes (Apache 2.0) |


## For Engineers

*Skip this section if you're not technical — see [ARCHITECTURE.md](ARCHITECTURE.md) for system design.*

### The Core Insight

**OpenHands SDK** provides **LLM abstraction**: swap Claude for GPT-4 or DeepSeek but always use OpenHands' agent logic, tools, and runtime.

This SDK provides **agent system abstraction**: use Anthropic's Claude Code agent, OpenAI's Codex agent, or OpenHands' agent, each with their own optimized logic, tools, and runtime.

The agent loop, prompts, and tool implementations are where the critical engineering effort lives. Anthropic has optimized Claude Code for enterprise coding while OpenHands has fine-tuned their model for SWE-bench. These are different systems, not just different LLMs.

### When to Use This SDK

- You need to switch between Claude Code, Codex, and OpenHands based on customer requirements.
- You want explicit validation loops with hard budget stops.
- You're integrating into LangGraph or PydantiAI workflows.

### When to Use the Backend SDKs Directly

- **Claude Agent SDK**: If you only need Claude Code and want Anthropic-specific features (hooks, subagents, MCP servers).
- **OpenHands SDK**: If OpenHands' agent logic is sufficient and you only need LLM-level flexibility.

### Competitive Positioning

| Project | Abstraction Level | Gap |
|---------|-------------------|-----|
| OpenHands SDK | LLM providers (100+ via LiteLLM) | Single agent system |
| Claude Agent SDK | Claude Code only | Single agent system |
| Codex SDK | Codex only | Single agent system |
| [OpenCode](https://github.com/sst/opencode) | LLM providers (Claude, OpenAI, Google, local) | Single agent system, TUI-focused |
| **This SDK** | Agent systems + validation | — |


## Document Index

| Document | Audience | Purpose |
|----------|----------|---------|
| [OVERVIEW.md](OVERVIEW.md) | Executives | Business case, value proposition (this document) |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Tech leads | System design, components, data flow |


## Related Work

### codex-as-a-service

A tool for batch Codex execution which is complementary to this SDK:

| Aspect | codex-as-a-service | This SDK |
|--------|-------------------|----------|
| Mode | Batch (many problems in parallel) | Single-task with iteration loop |
| Runtime | Docker containers | SDK wrappers |
| Backend | Codex only | Claude Code, Codex, OpenHands |
| Validation | Schema-based (post-hoc) | Syntax validation (with retry) |
| Use case | Dataset evaluation, benchmarks | Workflow integration, autonomous |

**Recommendation**: Use `codex-as-a-service` for batch evaluation runs; use this SDK for workflow integration and autonomous coding tasks.
