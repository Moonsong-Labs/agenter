"""Budget tracking for coding sessions."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from ..data_models.budget import BudgetLimitType

if TYPE_CHECKING:
    from ..data_models import Budget, UsageDelta


class BudgetMeter:
    """Tracks resource usage and checks budget limits.

    Monitors tokens, cost, time, and iterations against configured limits.

    Example:
        tracker = BudgetMeter(Budget(max_tokens=1000))
        tracker.add_usage(UsageDelta(tokens=500, cost_usd=0.25))
        tracker.add_iteration()
        exceeded, reason = tracker.exceeded()
        if exceeded:
            print(f"Limit hit: {reason.value}")  # e.g., "iterations"
    """

    def __init__(self, budget: Budget):
        self.budget = budget
        self.tokens_used = 0
        self.cost_usd = 0.0
        self.start_time = time.monotonic()  # Use monotonic for accurate duration
        self.iterations = 0

    def add_usage(self, delta: UsageDelta) -> None:
        """Add usage delta to tracked totals.

        Args:
            delta: Usage delta containing tokens and cost to add.
        """
        self.tokens_used += delta.tokens
        self.cost_usd += delta.cost_usd

    def add_iteration(self) -> None:
        """Record a completed iteration."""
        self.iterations += 1

    def exceeded(self) -> tuple[bool, BudgetLimitType | None]:
        """Check if any budget limit is exceeded.

        Returns:
            Tuple of (exceeded: bool, limit_type: BudgetLimitType | None)
        """
        if self.budget.max_iterations is not None and self.iterations >= self.budget.max_iterations:
            return True, BudgetLimitType.ITERATIONS
        if self.budget.max_tokens is not None and self.tokens_used >= self.budget.max_tokens:
            return True, BudgetLimitType.TOKENS
        if self.budget.max_cost_usd is not None and self.cost_usd >= self.budget.max_cost_usd:
            return True, BudgetLimitType.COST
        if self.budget.max_time_seconds is not None:
            elapsed = time.monotonic() - self.start_time
            if elapsed >= self.budget.max_time_seconds:
                return True, BudgetLimitType.TIME
        return False, None

    def usage(self) -> dict:
        """Return current usage statistics."""
        return {
            "tokens_used": self.tokens_used,
            "cost_usd": self.cost_usd,
            "elapsed_seconds": time.monotonic() - self.start_time,
            "iterations": self.iterations,
        }
