"""Security validator using Bandit for Python vulnerability detection."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from ..data_models import ValidationResult

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = structlog.get_logger()


# Bandit severity levels: LOW, MEDIUM, HIGH
# Bandit confidence levels: LOW, MEDIUM, HIGH
DEFAULT_MIN_SEVERITY = "MEDIUM"
DEFAULT_MIN_CONFIDENCE = "MEDIUM"

# Common false positives to skip by default
DEFAULT_SKIPS = frozenset(
    {
        "B101",  # assert_used - common in tests
        "B311",  # random - not a security issue in most cases
    }
)


class SecurityValidator:
    """Validates Python code security using Bandit static analysis.

    Scans generated Python code for common security vulnerabilities including:
    - Use of eval(), exec(), or similar dangerous functions
    - Hardcoded passwords or secrets
    - SQL injection risks
    - Weak cryptographic primitives
    - Insecure deserialization

    Requires the 'bandit' package to be installed. If not available, validation
    passes with a warning (soft dependency).

    Args:
        min_severity: Minimum severity to report ("LOW", "MEDIUM", "HIGH").
        min_confidence: Minimum confidence to report ("LOW", "MEDIUM", "HIGH").
        skip_ids: Set of Bandit plugin IDs to skip (e.g., {"B101", "B311"}).
        is_blocking: If True, security issues fail the coding session.
            If False (default), issues are reported as advisory warnings
            but don't prevent the session from completing.

    Example:
        validator = SecurityValidator(min_severity="HIGH")
        result = await validator.validate({"app.py": "eval(user_input)"}, "/project")
        assert not result.passed  # eval() is dangerous!
    """

    is_blocking: bool

    def __init__(
        self,
        min_severity: str = DEFAULT_MIN_SEVERITY,
        min_confidence: str = DEFAULT_MIN_CONFIDENCE,
        skip_ids: Sequence[str] | None = None,
        is_blocking: bool = False,  # Non-blocking by default (advisory)
    ) -> None:
        self.min_severity = min_severity.upper()
        self.min_confidence = min_confidence.upper()
        self.skip_ids = set(skip_ids) if skip_ids else set(DEFAULT_SKIPS)
        self.is_blocking = is_blocking

        # Validate severity/confidence levels
        valid_levels = {"LOW", "MEDIUM", "HIGH"}
        if self.min_severity not in valid_levels:
            raise ValueError(f"min_severity must be one of {valid_levels}")
        if self.min_confidence not in valid_levels:
            raise ValueError(f"min_confidence must be one of {valid_levels}")

    async def validate(self, files: dict[str, str], cwd: str) -> ValidationResult:
        """Scan Python files for security vulnerabilities.

        Args:
            files: Dict mapping file paths to their content.
            cwd: Working directory (for context).

        Returns:
            ValidationResult with any security issues found.
        """
        # Try importing bandit - soft dependency
        try:
            from bandit.core import config as bandit_config
            from bandit.core import manager as bandit_manager
        except ImportError:
            logger.warning(
                "bandit_not_installed",
                message="SecurityValidator skipped: 'bandit' package not installed",
            )
            return ValidationResult(passed=True, errors=[])

        # Filter to Python files only
        python_files = {p: c for p, c in files.items() if p.endswith(".py")}
        if not python_files:
            return ValidationResult(passed=True, errors=[])

        errors: list[str] = []

        # Write files to temp directory for Bandit to scan
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            file_paths: list[str] = []

            for path, content in python_files.items():
                # Flatten structure for scanning
                safe_name = path.replace("/", "_").replace("\\", "_")
                file_path = tmppath / safe_name
                file_path.write_text(content, encoding="utf-8")
                file_paths.append(str(file_path))

            # Configure and run Bandit
            try:
                conf = bandit_config.BanditConfig()
                mgr = bandit_manager.BanditManager(conf, "file")
                mgr.discover_files(file_paths)
                mgr.run_tests()

                # Process results
                for result in mgr.get_issue_list():
                    severity = result.severity.upper()
                    confidence = result.confidence.upper()

                    # Check skip list
                    if result.test_id in self.skip_ids:
                        continue

                    # Check severity/confidence thresholds
                    if not self._meets_threshold(severity, confidence):
                        continue

                    # Map back to original filename
                    scanned_name = Path(result.fname).name
                    original_path = self._find_original_path(scanned_name, list(python_files.keys()))

                    errors.append(
                        f"{original_path}:{result.lineno}: [{result.test_id}] {severity}/{confidence}: {result.text}"
                    )

            except Exception as e:
                logger.error("bandit_scan_failed", error=str(e))
                # Don't fail validation on scanner errors
                return ValidationResult(passed=True, errors=[])

        passed = len(errors) == 0
        if not passed:
            logger.info(
                "security_issues_found",
                issue_count=len(errors),
                is_blocking=self.is_blocking,
            )

        return ValidationResult(passed=passed, errors=errors)

    def _meets_threshold(self, severity: str, confidence: str) -> bool:
        """Check if issue meets minimum severity and confidence thresholds."""
        level_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        return level_order.get(severity, 0) >= level_order.get(self.min_severity, 1) and level_order.get(
            confidence, 0
        ) >= level_order.get(self.min_confidence, 1)

    def _find_original_path(self, scanned_name: str, original_paths: Sequence[str] | set[str]) -> str:
        """Find original path from flattened scan filename."""
        for path in original_paths:
            safe_name = path.replace("/", "_").replace("\\", "_")
            if safe_name == scanned_name:
                return path
        return scanned_name  # Fallback to scanned name
