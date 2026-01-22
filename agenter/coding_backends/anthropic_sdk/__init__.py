"""Anthropic SDK backend with custom tool loop.

This backend provides:
- Custom tool-use loop over the Anthropic SDK
- Strict path sandboxing via PathResolver
- Custom file tools (read, edit, write, list)
- Support for Anthropic API and AWS Bedrock

Use this backend when you need full control over tools and sandboxing.
"""

from .backend import AnthropicSDKBackend

__all__ = ["AnthropicSDKBackend"]
