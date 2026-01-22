"""Protocol for validators."""

from typing import Protocol

from ..data_models import ValidationResult


class Validator(Protocol):
    """Abstract interface for code validators.

    Validators check modified files and return pass/fail with error messages.
    """

    async def validate(self, files: dict[str, str], cwd: str) -> ValidationResult:
        """Validate modified files.

        Args:
            files: Dictionary of path -> content for modified files
            cwd: Working directory for context

        Returns:
            ValidationResult with passed status and any errors
        """
        ...
