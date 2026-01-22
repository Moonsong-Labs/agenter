"""Tests for the Anthropic and Bedrock client modules."""

from agenter.coding_backends.anthropic_sdk.client import (
    AnthropicClient,
    convert_tools_to_bedrock_format,
)


class TestAnthropicClient:
    """Test AnthropicClient class."""

    def test_lazy_initialization_returns_same_instance(self):
        """Client should lazily initialize and return same instance."""
        client = AnthropicClient()
        inner = client.get()
        inner2 = client.get()
        assert inner is inner2


class TestConvertToolsToBedrock:
    """Test convert_tools_to_bedrock_format function."""

    def test_empty_list(self):
        result = convert_tools_to_bedrock_format([])
        assert result == []

    def test_single_tool(self):
        tools = [
            {
                "name": "read_file",
                "description": "Read a file",
                "input_schema": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                },
            }
        ]
        result = convert_tools_to_bedrock_format(tools)
        assert len(result) == 1
        assert result[0]["toolSpec"]["name"] == "read_file"
        assert result[0]["toolSpec"]["description"] == "Read a file"
        assert "inputSchema" in result[0]["toolSpec"]

    def test_multiple_tools(self):
        tools = [
            {
                "name": "read_file",
                "description": "Read a file",
                "input_schema": {"type": "object"},
            },
            {
                "name": "write_file",
                "description": "Write a file",
                "input_schema": {"type": "object"},
            },
        ]
        result = convert_tools_to_bedrock_format(tools)
        assert len(result) == 2
        assert result[0]["toolSpec"]["name"] == "read_file"
        assert result[1]["toolSpec"]["name"] == "write_file"

    def test_skips_special_types(self):
        """Tools with 'type' field (like text_editor) should be skipped."""
        tools = [
            {"type": "text_editor_20250728", "name": "text_editor"},
            {
                "name": "read_file",
                "description": "Read a file",
                "input_schema": {"type": "object"},
            },
        ]
        result = convert_tools_to_bedrock_format(tools)
        assert len(result) == 1
        assert result[0]["toolSpec"]["name"] == "read_file"
