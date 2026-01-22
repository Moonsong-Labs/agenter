"""Syntax validator for Python files."""

import ast

from ..data_models import ValidationResult


class SyntaxValidator:
    """Validates Python syntax using AST parsing.

    Fast, zero-dependency validation that catches syntax errors immediately.
    """

    is_blocking: bool = True

    async def validate(self, files: dict[str, str], cwd: str) -> ValidationResult:
        """Check Python files for syntax errors."""
        errors = []

        for path, content in files.items():
            if not path.endswith(".py"):
                continue

            try:
                ast.parse(content, filename=path)
            except SyntaxError as e:
                line = e.lineno or 0
                msg = e.msg or "syntax error"
                errors.append(f"{path}:{line}: {msg}")

        return ValidationResult(passed=len(errors) == 0, errors=errors)
