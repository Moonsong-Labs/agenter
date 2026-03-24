---
name: agenter-coder
description: >-
  Execute autonomous coding tasks using Agenter, a backend-agnostic SDK
  supporting Claude Code, Codex, OpenHands, and Anthropic SDK. Use when the
  user asks to write, generate, refactor, or fix code in a project. Delegates
  to a specialized coding agent with validation, budget controls, and sandboxing.
tags: [coding, agent, code-generation, refactoring, autonomous, claude, codex, openhands]
user-invocable: true
metadata:
  openclaw:
    primaryEnv: ANTHROPIC_API_KEY
    requires:
      bins: [python3, uv]
    installer:
      - type: command
        command: "uv pip install agenter>=0.1.1"
---

# Agenter Coder

You have access to an autonomous AI coding agent via the Agenter SDK. This agent
is purpose-built for code generation — it has its own tool loop, file operations,
validation, and retry logic. Delegate coding work to it instead of writing files
one at a time.

## When to use

Use this skill when the user asks to:
- Write, create, or generate code for a project
- Modify, refactor, or update existing code
- Fix bugs in a codebase
- Create entire applications or components
- Generate tests for existing code

Do NOT use for: reading files, explaining code, or answering questions about code.
Use your own tools for those.

## How to run

```bash
python3 {SKILL_DIR}/scripts/agenter_cli.py \
  --prompt "<the coding task>" \
  --cwd "<workspace directory>" \
  --backend "anthropic-sdk" \
  --max-cost-usd 2.0 \
  --max-iterations 5 \
  --sandbox
```

## Parameters

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--prompt` | Yes | — | The coding task. Be specific about what to build. |
| `--cwd` | Yes | — | Working directory. Use the current workspace or a subdirectory. |
| `--backend` | No | `anthropic-sdk` | Runtime: `anthropic-sdk`, `claude-code`, `codex`, or `openhands`. |
| `--model` | No | auto | Model override (e.g., `claude-sonnet-4-20250514`). |
| `--max-cost-usd` | No | unlimited | Maximum spend in USD. |
| `--max-tokens` | No | unlimited | Maximum total tokens (input + output). |
| `--max-time-seconds` | No | unlimited | Maximum wall clock time. |
| `--max-iterations` | No | `5` | Max validation/retry iterations. |
| `--allowed-write-paths` | No | all in cwd | Glob patterns for allowed writes (e.g., `"*.py" "*.ts"`). |
| `--sandbox` / `--no-sandbox` | No | `--sandbox` | Sandboxed execution (recommended). |
| `--stream` | No | off | Emit NDJSON progress events for real-time updates. |

## Cost awareness

Set budget limits based on task complexity. Always tell the user the estimated cost.

| Task type | Suggested `--max-cost-usd` | Suggested `--max-iterations` |
|-----------|---------------------------|------------------------------|
| Simple script / single file | 0.50 | 3 |
| Small app / multiple files | 2.00 | 5 |
| Complex refactoring / full project | 5.00 | 7 |

## Backend selection

Default to `anthropic-sdk` unless the user asks for a specific backend. Check
`{SKILL_DIR}/references/backends.md` if the user asks about backend differences.

- **anthropic-sdk** — Default. Works with `ANTHROPIC_API_KEY`. Best for most tasks.
- **claude-code** — Requires Claude Code CLI. Battle-tested file tools and native sandbox.
- **codex** — Requires `OPENAI_API_KEY`. Use for OpenAI models (o3, GPT).
- **openhands** — Requires OpenHands runtime. Any model via litellm. Must use `--no-sandbox`.

## Reading the output

The script outputs JSON to stdout:

```json
{
  "status": "completed",
  "summary": "Created main.py with FastAPI app and test_main.py",
  "files_modified": ["main.py", "test_main.py"],
  "files": {"main.py": "...", "test_main.py": "..."},
  "iterations": 2,
  "total_tokens": 15000,
  "total_cost_usd": 0.045,
  "total_duration_seconds": 12.3
}
```

### Status values

| Status | Meaning | What to do |
|--------|---------|------------|
| `completed` | Task succeeded, files written to disk. | Report summary and files to user. |
| `completed_with_limit_exceeded` | Task succeeded but used more resources than configured. | Report success + warn about cost. |
| `budget_exceeded` | Stopped because budget ran out before completion. | Tell user, ask if they want to retry with higher budget. |
| `refused` | The model refused the request (safety/policy). | Report refusal reason to user. |
| `failed` | Unrecoverable error. | Report error, suggest checking logs. |

## After running

1. Check the `status` field.
2. If `completed`: the files are already written to disk in `--cwd`. Use `read` to
   inspect them if the user wants to review.
3. Report the **summary**, **cost**, and **files modified** to the user.
4. If `failed` or `budget_exceeded`: report the issue and ask how to proceed.
