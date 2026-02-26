"""
Tool Registry - Register and execute tools that LLMs can call.

Equivalent to Vercel AI SDK's tool() function and Zod schema validation.
Uses Pydantic for schema validation instead of Zod.

Usage:
    from chat_sdk.services import ToolRegistry, chat_tool
    from pydantic import BaseModel, Field

    class WeatherParams(BaseModel):
        city: str = Field(description="The city name")
        unit: str = Field(default="celsius", description="Temperature unit")

    @chat_tool(
        name="get_weather",
        description="Get current weather for a city",
        parameters=WeatherParams,
    )
    async def get_weather(city: str, unit: str = "celsius"):
        return {"temperature": 72, "condition": "sunny", "unit": unit}

    # Register
    registry = ToolRegistry()
    registry.register(get_weather)
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """A registered tool with its schema and execute function."""

    name: str
    description: str
    parameters_schema: dict[str, Any]  # JSON Schema
    execute_fn: Callable
    is_async: bool = False

    def to_openai_tool(self) -> dict:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }


def chat_tool(name: str, description: str, parameters=None):
    """
    Decorator to register a function as a chat tool.

    Args:
        name: Tool name (used in LLM tool calls)
        description: Human-readable description for the LLM
        parameters: Pydantic BaseModel class for parameter validation
    """
    def decorator(fn):
        schema = {}
        if parameters is not None:
            schema = parameters.model_json_schema()

        fn._tool_definition = ToolDefinition(
            name=name,
            description=description,
            parameters_schema=schema,
            execute_fn=fn,
            is_async=asyncio.iscoroutinefunction(fn),
        )
        return fn
    return decorator


class ToolRegistry:
    """
    Registry for chat tools. Manages tool definitions and execution.

    Equivalent to Vercel AI SDK's tools parameter in generateText/streamText.
    """

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, fn_or_definition):
        """Register a tool (decorated function or ToolDefinition)."""
        if isinstance(fn_or_definition, ToolDefinition):
            defn = fn_or_definition
        elif hasattr(fn_or_definition, "_tool_definition"):
            defn = fn_or_definition._tool_definition
        else:
            raise ValueError(
                f"Cannot register {fn_or_definition}. "
                "Use @chat_tool decorator or pass a ToolDefinition."
            )

        self._tools[defn.name] = defn
        logger.debug(f"Registered tool: {defn.name}")

    def unregister(self, name: str):
        """Remove a tool from the registry."""
        self._tools.pop(name, None)

    def get(self, name: str) -> ToolDefinition | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def to_openai_tools(self) -> list[dict]:
        """Convert all tools to OpenAI function calling format."""
        return [tool.to_openai_tool() for tool in self._tools.values()]

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """
        Execute a tool by name with the given arguments.

        Args:
            tool_name: Name of the registered tool
            arguments: Dict of arguments (from LLM tool call)

        Returns:
            Tool execution result

        Raises:
            KeyError: If tool not found
            ValueError: If arguments fail validation
        """
        tool = self._tools.get(tool_name)
        if not tool:
            raise KeyError(f"Tool '{tool_name}' not found in registry")

        # Parse string arguments if needed
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}

        logger.info(f"Executing tool: {tool_name} with args: {arguments}")

        try:
            if tool.is_async:
                result = await tool.execute_fn(**arguments)
            else:
                # Run sync functions in thread pool
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, lambda: tool.execute_fn(**arguments)
                )
            return result
        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name} - {e}")
            return {"error": str(e)}

    def has_tools(self) -> bool:
        """Check if any tools are registered."""
        return len(self._tools) > 0


# Global tool registry instance
default_registry = ToolRegistry()
