"""Validator chain for pluggable validation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ..data_models import ValidationResult  # noqa: TC001 - required at runtime by Pydantic

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .protocol import Validator


class ValidatorOutcome(BaseModel):
    """Result from a single validator.

    Attributes:
        name: The validator class name.
        result: The validation result from that validator.
    """

    model_config = {"arbitrary_types_allowed": True}

    name: str
    result: ValidationResult


class ChainValidationResult(BaseModel):
    """Result from running the validator chain.

    Includes both aggregate results and per-validator breakdowns for observability.

    Attributes:
        passed: True if all blocking validators passed. Advisory (non-blocking)
            validator errors are reported but don't affect this flag.
        errors: All error messages (both blocking and advisory).
        advisory_errors: Errors from non-blocking validators only (informational).
        validator_results: List of outcomes from each validator that ran.
    """

    passed: bool
    errors: list[str] = Field(default_factory=list)
    advisory_errors: list[str] = Field(default_factory=list)
    validator_results: list[ValidatorOutcome] = Field(default_factory=list)


class ValidatorChain:
    """Runs validators in sequence, aggregating errors.

    Short-circuits after blocking validation failure (e.g., syntax errors)
    since there's no point running further validators on invalid code.

    Example:
        chain = ValidatorChain([SyntaxValidator()])
        result = await chain.validate(files, cwd)
        if not result.passed:
            print(result.errors)
    """

    def __init__(self, validators: Sequence[Validator]) -> None:
        """Initialize with validators to run.

        Args:
            validators: Sequence of validators to run in order.
        """
        self.validators = validators

    async def validate(
        self,
        files: dict[str, str],
        cwd: str,
    ) -> ChainValidationResult:
        """Run all validators, aggregating errors.

        Args:
            files: Dictionary of path -> content for modified files.
            cwd: Working directory for context.

        Returns:
            ChainValidationResult with combined pass/fail, all errors,
            and per-validator breakdown for observability.

        Note:
            - Blocking validators (is_blocking=True): errors fail the run
            - Advisory validators (is_blocking=False): errors are reported
              but don't affect pass/fail status
        """
        blocking_errors: list[str] = []
        advisory_errors: list[str] = []
        validator_results: list[ValidatorOutcome] = []

        for validator in self.validators:
            result = await validator.validate(files, cwd)
            validator_name = validator.__class__.__name__
            validator_results.append(ValidatorOutcome(name=validator_name, result=result))

            if not result.passed:
                is_blocking = getattr(validator, "is_blocking", True)  # Default to blocking
                if is_blocking:
                    blocking_errors.extend(result.errors)
                    # Short-circuit: no point running more validators if blocking failed
                    break
                else:
                    # Advisory: collect errors but don't fail the run
                    advisory_errors.extend(result.errors)

        return ChainValidationResult(
            passed=len(blocking_errors) == 0,
            errors=blocking_errors + advisory_errors,  # All errors for display
            advisory_errors=advisory_errors,
            validator_results=validator_results,
        )
