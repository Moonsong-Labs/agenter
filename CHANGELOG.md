# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2025-01-22

### Added
- Initial release of Agenter SDK
- Core `Agent` abstraction with unified interface for coding agents
- Support for multiple backends:
  - Anthropic API (direct)
  - AWS Bedrock
  - Claude Code CLI
  - OpenAI Codex
- Budget controls with `BudgetConfig` for cost limits and token tracking
- Security validation framework with configurable validators
- Path validation to restrict file system access
- Streaming support with real-time output callbacks
- Framework adapters for PydanticAI and LangGraph integration
- Comprehensive type hints and Pydantic models
- Structured logging with structlog

[Unreleased]: https://github.com/moonsong-labs/agenter/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/moonsong-labs/agenter/releases/tag/v0.1.0
