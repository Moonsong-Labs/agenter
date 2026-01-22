"""Framework adapters for integrating Agenter with popular frameworks.

Available adapters:
- langgraph: Create LangGraph nodes for autonomous coding workflows
- pydantic_ai: CodingAgent class for pydantic-ai workflows

Note: These adapters require optional dependencies to be installed.
Install with: pip install agenter[pydantic-ai] or [langgraph]

Example (LangGraph):
    from agenter.adapters.langgraph import create_coding_node, CodingState

    graph = StateGraph(CodingState)
    graph.add_node("coder", create_coding_node(cwd="./workspace"))

Example (PydanticAI):
    from agenter.adapters.pydantic_ai import CodingAgent

    agent = CodingAgent(cwd="./workspace")
    result = await agent.run("Add input validation")
"""

# Adapters are imported lazily to avoid requiring optional dependencies
__all__: list[str] = []
