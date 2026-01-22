"""Budget limit types for the SDK."""

from enum import Enum


class BudgetLimitType(str, Enum):
    """Types of budget limits that can be exceeded.

    Used by BudgetMeter.exceeded() to indicate which limit was hit.
    """

    ITERATIONS = "iterations"
    TOKENS = "tokens"
    COST = "cost"
    TIME = "time"
