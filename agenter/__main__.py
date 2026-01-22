"""CLI entry point for testing the SDK."""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

# Optionally clear Claude Code env vars (they may conflict with project .env)
# Enable with: ACA_CLEAR_CLAUDE_ENV=1 python -m agenter
if os.environ.get("ACA_CLEAR_CLAUDE_ENV") == "1":
    for var in [
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_BEDROCK_BASE_URL",
        "CLAUDE_CODE_USE_BEDROCK",
        "AWS_BEARER_TOKEN_BEDROCK",
        "AWS_REGION",
    ]:
        os.environ.pop(var, None)

# Load project .env if it exists
try:
    from dotenv import load_dotenv

    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=True)
except ImportError:
    pass  # dotenv not installed, skip

from . import AutonomousCodingAgent, CodingRequest, CodingStatus


def main() -> None:
    from .config import DEFAULT_MAX_ITERATIONS, default_model

    model = default_model()

    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Create hello.py with a greet(name) function"

    print(f"Model: {model}")
    print(f"Prompt: {prompt}")
    print()

    async def run() -> int:
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = AutonomousCodingAgent(model=model)
            result = await agent.execute(
                CodingRequest(
                    prompt=prompt,
                    cwd=tmpdir,
                    max_iterations=DEFAULT_MAX_ITERATIONS,
                )
            )

            print(f"Status: {result.status.value}")
            print(f"Iterations: {result.iterations}")
            print(f"Tokens: {result.total_tokens}")
            print()

            for path, content in result.files.items():
                print(f"--- {path} ---")
                print(content)
                print()

            return 0 if result.status == CodingStatus.COMPLETED else 1

    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
