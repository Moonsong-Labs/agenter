"""Tests for the config module."""

import os
from unittest.mock import patch

from agenter.config import (
    default_model,
    is_bedrock,
)


class TestIsBedrock:
    """Test is_bedrock function."""

    def test_returns_false_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            # Remove the key if it exists
            os.environ.pop("AWS_BEARER_TOKEN_BEDROCK", None)
            assert is_bedrock() is False

    def test_returns_true_when_env_set(self):
        with patch.dict(os.environ, {"AWS_BEARER_TOKEN_BEDROCK": "some-token"}):
            result = is_bedrock()
            assert result is True


class TestDefaultModel:
    """Test default_model function."""

    def test_returns_different_models_based_on_environment(self):
        """Default model should differ based on Bedrock environment."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("AWS_BEARER_TOKEN_BEDROCK", None)
            anthropic_model = default_model()

        with patch.dict(os.environ, {"AWS_BEARER_TOKEN_BEDROCK": "token"}):
            bedrock_model = default_model()

        # Models should be different for different backends
        assert anthropic_model != bedrock_model
