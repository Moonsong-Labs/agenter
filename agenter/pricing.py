"""Model pricing using litellm.

This module provides cost calculation for API calls using litellm's
actively maintained pricing database covering 100+ models.

Note: litellm is imported lazily to avoid import-time overhead.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


def calculate_cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Calculate cost in USD for token usage.

    Uses litellm's pricing database which is actively maintained
    and covers Anthropic, OpenAI, Bedrock, and many other providers.

    Args:
        model: Model identifier (Anthropic or Bedrock format).
        input_tokens: Number of input tokens used.
        output_tokens: Number of output tokens generated.

    Returns:
        Estimated cost in USD. Returns 0.0 if litellm is not installed
        or for unknown models.
    """
    try:
        from litellm import cost_per_token  # Lazy import to reduce startup time

        prompt_cost, completion_cost = cost_per_token(
            model=model,
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
        )
        return prompt_cost + completion_cost
    except ImportError:
        logger.debug("litellm not installed, returning 0.0 cost")
        return 0.0
    except Exception as e:
        logger.warning("cost_calculation_failed", model=model, error=str(e))
        return 0.0
