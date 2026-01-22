# Naming Conventions

## TL;DR

This document provides some guidelines for contributors. 

## General

Every name and naming pattern should tell your reader *what* something does - not *where* it lives.

## Avoid

These descriptors are weak and underspecified. Please avoid them:

| Term | Smell | Use Instead |
|--------|-----|-------------|
| `get_*` | Weak; everything ultimately "gets" something | Use a noun: `usage()` not `get_usage()` |
| `core` | Weak; everything is ultimately "core" depending on the viewpoint | Name by purpose: `types`, `session` |
| `utils` | A classic dumping ground | Name by function: `output_parser`, `path_resolver` |
| `helpers` | A classic dumping ground | Be specific: `prompt_builder`, `token_counter` |
| `common` | Vague | Name the actual abstraction |
| `misc` | Weak | Split into meaningful modules |
| `manager` | A classic dumping ground and a God object | Use specific nouns: `Registry`, `Pool`, `Scheduler` |
| `handler` | Vague | Name the actor or action: `Detector`, `Parser`, `Dispatcher` |
| `do_*` | Weak | Use a specific verb |
| `process_*` | Vague | `parse_*`, `transform_*`, `validate_*` |
| `*data*` | Vague | Name what the data represents |


## Verb Prefixes

For action-oriented names (functions, methods), use verbs that convey a specific **intent**:

| Verb | Meaning | Example |
|------|---------|---------|
| `fetch_*` | Retrieve from external source (API, network) | `fetch_model_response()` |
| `read_*` | Load from local source (file, memory) | `read_config()` |
| `compute_*` | Derive a value through calculation | `compute_cost()` |
| `parse_*` | Convert raw, unstructured data to a (more) structured form | `parse_mcp_event()` |
| `build_*` | Construct a complex object step by step | `build_prompt()` |
| `validate_*` | Check correctness, return bool or raise | `validate_syntax()` |
| `emit_*` | Send an event or signal outwards | `emit_iteration_completed()` |
| `track_*` | Record a state change for later use | `track_modified_file()` |
| `resolve_*` | Convert a reference to a concrete value | `resolve_path()` |
| `extract_*` | Pull specific data from a larger structure | `extract_tool_calls()` |


## Accessor Patterns

| Pattern | When | Example |
|---------|------|---------|
| `@property noun` | Operations that are lightweight, cached, or computed once | `total_tokens`, `is_connected` |
| `noun()` method | Returning state, no side effects | `usage()`, `modified_files()` |
| `compute_*()` | Expensive calculations | `compute_estimated_cost()` |
| `fetch_*()` | Involves network I/O | `fetch_remote_config()` |

If something accesses a network or disk, use a verb. If it returns a state, use a noun.


## Event Classes (DDD Patterns)

Events represent **something that has happened**. Name them in the **past tense**:

| Pattern | Example |
|---------|---------|
| `{What}{PastVerb}` | `SessionStarted`, `TaskCompleted` |
| `{What}{PastVerb}` | `MessageReceived`, `RequestRefused` |

**Examples:**
```python
class SessionStarted(BaseModel): ...
class IterationCompleted(BaseModel): ...
class ValidationCompleted(BaseModel): ...
class TaskFailed(BaseModel): ...
```

**Avoid**: `SessionStartData`, `IterationEndData`, `CompletedData`


## Class Suffixes

| Type | Suffix | Examples |
|------|--------|----------|
| Backends | `*Backend` | `AnthropicSDKBackend`, `ClaudeCodeBackend`, `CodexBackend` |
| Exceptions | `*Error` | `BackendError`, `ConfigurationError` |
| Results | `*Result` | `CodingResult`, `ValidationResult` |
| Messages | `*Message` | `TextMessage`, `ToolCallMessage` |
| Configs and settings | `*Config` or `*Options` | `BackendConfig`, `SandboxOptions` |
| Protocols | (no suffix) | `CodingBackend`, `Validator`, `Tracer` |
| Detectors and analyzers | `*Detector`, `*Analyzer` | `RefusalDetector`, `SyntaxAnalyzer` |


## Binary Names

| Prefix | Use For | Example |
|--------|---------|---------|
| `is_*` | State checks | `is_connected`, `is_valid` |
| `has_*` | Possession and inclusion checks | `has_errors`, `has_content` |
| `can_*` | Capability and potential checks | `can_retry`, `can_write` |
| `should_*` | Policy and behavior decisions | `should_sandbox`, `should_retry` |

**Avoid**: `check_*` returning a bool (instead use `check_*` for void functions that raise errors)


## Module Names

| Pattern | Meaning | Example |
|---------|---------|---------|
| `{noun}.py` | A specific single concept| `session.py`, `budget.py` |
| `{noun}_{role}.py` | A concept and its role | `output_parser.py`, `path_resolver.py` |
| `{verb}ing.py` | A process-oriented module | `streaming.py`, `tracing.py` |

**Avoid**: `*_utils.py`, `*_helpers.py`, `*_common.py`, `core.py`


## Constant Names

```python
# Module-level constants: SCREAMING_SNAKE with a Final type hint
DEFAULT_MAX_ITERATIONS: Final[int] = 5
DEFAULT_MODEL: Final[str] = "claude-sonnet-4-20250514"

# Private constants: underscore prefix
_MCP_TIMEOUT_MS: Final[int] = 30000
```

## Test Names

```python
# Class names: Test{ClassUnderTest}
class TestBudgetMeter:

    # Method names: test_{behavior} or test_{method}_{scenario}
    def test_tracks_token_usage(self): ...
    def test_exceeded_when_over_limit(self): ...

    # Async names: same pattern
    async def test_streams_backend_messages(self): ...
```

**Avoid**: `test_1`, `test_basic`, `test_it_works`

## Additional Tips

- **No `get_*`**
    - use noun methods or properties
- **No `core`, `utils`, `helpers`**
    - name by purpose
- **No `*Data`**
- **Events are past facts**
    - `SessionStarted`, `TaskCompleted`, `RequestRefused`
- **Verbs convey I/O**
    - `fetch_*` (network), `read_*` (file), `compute_*` (CPU)
- **Nouns convey roles**
    - `*Backend`, `*Result`, `*Error`, `*Message`
- **Booleans are questions**
    - `is_*`, `has_*`, `can_*`, `should_*`
