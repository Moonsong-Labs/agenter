"""Tests for SecurityValidator."""

import pytest

from agenter.post_validators.security import (
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_MIN_SEVERITY,
    DEFAULT_SKIPS,
    SecurityValidator,
)


class TestSecurityValidatorConfig:
    """Test SecurityValidator configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        validator = SecurityValidator()
        assert validator.min_severity == DEFAULT_MIN_SEVERITY
        assert validator.min_confidence == DEFAULT_MIN_CONFIDENCE
        assert validator.skip_ids == set(DEFAULT_SKIPS)
        assert not validator.is_blocking

    def test_custom_config(self):
        """Test custom configuration."""
        validator = SecurityValidator(
            min_severity="HIGH",
            min_confidence="LOW",
            skip_ids=["B001", "B002"],
            is_blocking=True,
        )
        assert validator.min_severity == "HIGH"
        assert validator.min_confidence == "LOW"
        assert validator.skip_ids == {"B001", "B002"}
        assert validator.is_blocking

    def test_invalid_severity_raises(self):
        """Invalid severity should raise ValueError."""
        with pytest.raises(ValueError, match="min_severity must be one of"):
            SecurityValidator(min_severity="CRITICAL")

    def test_invalid_confidence_raises(self):
        """Invalid confidence should raise ValueError."""
        with pytest.raises(ValueError, match="min_confidence must be one of"):
            SecurityValidator(min_confidence="VERY_HIGH")

    def test_severity_case_insensitive(self):
        """Severity should be case-insensitive."""
        validator = SecurityValidator(min_severity="high")
        assert validator.min_severity == "HIGH"


class TestSecurityValidatorValidation:
    """Test actual validation functionality."""

    @pytest.mark.asyncio
    async def test_empty_files_passes(self):
        """No files to scan should pass."""
        validator = SecurityValidator()
        result = await validator.validate({}, "/tmp")
        assert result.passed
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_non_python_files_ignored(self):
        """Non-Python files should be ignored."""
        validator = SecurityValidator()
        result = await validator.validate(
            {
                "script.js": "eval(user_input)",  # Would be bad in Python
                "config.yaml": "password: secret",
            },
            "/tmp",
        )
        assert result.passed

    @pytest.mark.asyncio
    async def test_clean_python_passes(self):
        """Clean Python code should pass."""
        validator = SecurityValidator()
        result = await validator.validate(
            {
                "main.py": "def hello():\n    print('Hello, world!')\n",
                "utils.py": "import os\npath = os.getcwd()\n",
            },
            "/tmp",
        )
        assert result.passed

    @pytest.mark.asyncio
    async def test_bandit_not_installed_passes(self, monkeypatch):
        """If bandit is not installed, should pass with warning."""
        import builtins
        import sys

        # Temporarily make bandit import fail
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name.startswith("bandit"):
                raise ImportError("Mocked: bandit not installed")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        # Clear any cached bandit imports
        for key in list(sys.modules.keys()):
            if key.startswith("bandit"):
                del sys.modules[key]

        validator = SecurityValidator()
        result = await validator.validate(
            {"bad.py": "eval(user_input)"},
            "/tmp",
        )
        # Should pass because bandit is "not available"
        assert result.passed
