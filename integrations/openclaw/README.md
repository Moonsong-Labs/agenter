# Agenter Coder — OpenClaw Skill

An [OpenClaw](https://openclaw.ai) skill that gives your agent autonomous coding
capabilities powered by [Agenter](https://github.com/moonsonglabs/agenter).

Instead of writing code file-by-file, your OpenClaw agent delegates to a
specialized coding agent with its own tool loop, validation, and retry logic.

## What it does

When a user asks OpenClaw to write, generate, or fix code, this skill:

1. Spawns an autonomous coding agent (via Agenter SDK)
2. The coding agent writes/edits files, runs commands, and validates its work
3. Returns the results (status, files modified, cost) back to OpenClaw
4. OpenClaw presents the results to the user

## Backends

Switch between AI providers with a single parameter:

| Backend | Provider | Models |
|---------|----------|--------|
| `anthropic-sdk` | Anthropic | Claude Sonnet, Opus, Haiku |
| `claude-code` | Anthropic | Claude Code's native runtime |
| `codex` | OpenAI | o3, GPT-4o |
| `openhands` | Any | Any model via litellm |

## Installation

### From ClawHub

```bash
clawhub install agenter-coder
```

### From this repo

Clone the agenter repo and copy the skill into your OpenClaw workspace:

```bash
git clone https://github.com/moonsonglabs/agenter.git
cp -r agenter/integrations/openclaw ~/.openclaw/workspace/skills/agenter-coder
```

### Configuration

Add to your `openclaw.json`:

```json
{
  "skills": {
    "entries": {
      "agenter-coder": {
        "enabled": true,
        "env": {
          "ANTHROPIC_API_KEY": "your-key-here"
        }
      }
    }
  }
}
```

Install the Python dependency:

```bash
uv pip install agenter>=0.1.1
```

Restart your OpenClaw session after installing.

## Publishing to ClawHub

Prerequisites: OpenClaw CLI installed (`curl -sSL https://openclaw.ai/install | bash`),
GitHub account (1+ week old).

```bash
# 1. Authenticate (opens browser for GitHub OAuth — one time only)
clawhub login
clawhub whoami                # verify it worked

# 2. Publish directly from the skill directory
clawhub publish ./integrations/openclaw \
  --slug agenter-coder \
  --name "Agenter Coder" \
  --version 1.0.0 \
  --tags latest

# 3. Verify
clawhub list                  # should show agenter-coder
```

Users can then install with `clawhub install agenter-coder`.

## Usage

Once installed, just ask your OpenClaw agent to code:

> "Create a FastAPI app with a health check endpoint"

> "Fix the bug in the login handler"

> "Refactor the database module to use async queries"

Or use the slash command:

> `/code Create a REST API for managing todos`

The agent automatically selects appropriate budget limits based on task complexity.

## Budget controls

Every coding task runs with configurable limits to prevent runaway costs:

- **max_cost_usd** — Cap spending in USD
- **max_tokens** — Cap total token usage
- **max_time_seconds** — Cap wall clock time
- **max_iterations** — Cap validation/retry cycles

## Links

- [Agenter SDK](https://github.com/moonsonglabs/agenter) — The underlying coding agent SDK
- [OpenClaw](https://openclaw.ai) — The AI agent platform
- [ClawHub](https://clawhub.openclaw.ai) — Skill registry
