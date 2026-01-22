"""Shared utilities for coding backends."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import structlog
from pydantic import ValidationError

if TYPE_CHECKING:
    from pydantic import BaseModel

logger = structlog.get_logger(__name__)


def parse_structured_output(
    text: str | None,
    output_type: type[BaseModel] | None,
) -> BaseModel | None:
    """Parse text content as structured output.

    Args:
        text: The text content to parse (typically last response text).
        output_type: The Pydantic model class to validate against.

    Returns:
        Parsed model instance, or None if parsing fails or inputs are None.
    """
    if output_type is None or not text:
        return None

    # Try direct parse first (pure JSON)
    try:
        return output_type.model_validate_json(text)
    except (json.JSONDecodeError, ValidationError):
        pass

    # Extract JSON from markdown code blocks (```json ... ``` or ``` ... ```)
    code_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
    matches = re.findall(code_block_pattern, text, re.DOTALL)
    for match in matches:
        try:
            return output_type.model_validate_json(match.strip())
        except (json.JSONDecodeError, ValidationError):
            pass

    # Find JSON object in mixed content using raw_decode
    decoder = json.JSONDecoder()
    idx = text.find("{")
    while idx != -1:
        try:
            obj, _ = decoder.raw_decode(text, idx)
            if isinstance(obj, dict):
                return output_type.model_validate(obj)
        except json.JSONDecodeError:
            pass
        idx = text.find("{", idx + 1)

    return None
