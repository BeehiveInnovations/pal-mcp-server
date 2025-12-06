"""
Simple tools for PAL MCP.

Simple tools follow a basic request → AI model → response pattern.
They inherit from SimpleTool which provides streamlined functionality
for tools that don't need multi-step workflows.

Available simple tools:
- chat: General chat and collaborative thinking
- consensus: Multi-perspective analysis
- listmodels: Model listing and information
- testgen: Test generation
- tracer: Execution tracing
"""

from .base import SimpleTool

__all__ = ["SimpleTool"]
