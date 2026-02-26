"""
Anthropic provider adapter.

Equivalent to Vercel AI SDK's @ai-sdk/anthropic package.
Uses the official anthropic Python SDK.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator

from .base import BaseProvider, GenerateResult

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseProvider):
    """
    Anthropic (Claude) provider using the official Python SDK.

    Config:
        api_key: Anthropic API key
        base_url: Optional custom base URL
        max_tokens: Default max tokens (required by Anthropic API)
    """

    provider_name = "anthropic"

    def __init__(self, model_id: str = "claude-sonnet-4-20250514", **config):
        super().__init__(model_id=model_id, **config)
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
            except ImportError:
                raise ImportError("anthropic package required: pip install anthropic")

            self._client = AsyncAnthropic(
                api_key=self.config.get("api_key"),
                base_url=self.config.get("base_url"),
            )
        return self._client

    def _convert_messages(self, messages: list[dict]) -> tuple[str, list[dict]]:
        """
        Convert OpenAI-format messages to Anthropic format.

        Returns:
            (system_prompt, messages) tuple
        """
        system_prompt = ""
        anthropic_messages = []

        for msg in messages:
            role = msg.get("role", "user")

            if role == "system":
                system_prompt += msg.get("content", "") + "\n"
                continue

            if role == "tool":
                # Anthropic uses tool_result content blocks
                anthropic_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.get("tool_call_id", ""),
                        "content": msg.get("content", ""),
                    }],
                })
                continue

            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls", [])

            if role == "assistant" and tool_calls:
                # Convert OpenAI tool_calls to Anthropic tool_use blocks
                blocks = []
                if content:
                    blocks.append({"type": "text", "text": content})
                for tc in tool_calls:
                    func = tc.get("function", {})
                    args = func.get("arguments", "{}")
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {}
                    blocks.append({
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": func.get("name", ""),
                        "input": args,
                    })
                anthropic_messages.append({"role": "assistant", "content": blocks})
            else:
                # Handle multimodal content
                if isinstance(content, list):
                    blocks = []
                    for item in content:
                        if item.get("type") == "text":
                            blocks.append({"type": "text", "text": item["text"]})
                        elif item.get("type") == "image_url":
                            url = item.get("image_url", {}).get("url", "")
                            if url.startswith("data:"):
                                media_type, data = url.split(";base64,", 1)
                                media_type = media_type.replace("data:", "")
                                blocks.append({
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": media_type,
                                        "data": data,
                                    },
                                })
                            else:
                                blocks.append({
                                    "type": "image",
                                    "source": {"type": "url", "url": url},
                                })
                    anthropic_messages.append({"role": role, "content": blocks})
                else:
                    anthropic_messages.append({"role": role, "content": content})

        return system_prompt.strip(), anthropic_messages

    def _convert_tools(self, tools: list[dict] | None) -> list[dict] | None:
        """Convert OpenAI tool format to Anthropic format."""
        if not tools:
            return None

        anthropic_tools = []
        for tool in tools:
            func = tool.get("function", {})
            anthropic_tools.append({
                "name": func.get("name", ""),
                "description": func.get("description", ""),
                "input_schema": func.get("parameters", {}),
            })
        return anthropic_tools

    async def generate(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        tools: list[dict] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs,
    ) -> GenerateResult:
        client = self._get_client()
        system, conv_messages = self._convert_messages(messages)

        params = {
            "model": self.get_model(model),
            "messages": conv_messages,
            "max_tokens": max_tokens or self.config.get("max_tokens", 4096),
        }

        if system:
            params["system"] = system
        if temperature is not None:
            params["temperature"] = temperature

        anthropic_tools = self._convert_tools(tools)
        if anthropic_tools:
            params["tools"] = anthropic_tools

        response = await client.messages.create(**params)

        content = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "tool_call_id": block.id,
                    "tool_name": block.name,
                    "args": block.input,
                })

        return GenerateResult(
            content=content,
            tool_calls=tool_calls,
            finish_reason=response.stop_reason or "end_turn",
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
            },
            metadata={"model": response.model, "id": response.id},
        )

    async def stream(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        tools: list[dict] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs,
    ) -> AsyncGenerator[dict, None]:
        client = self._get_client()
        system, conv_messages = self._convert_messages(messages)

        params = {
            "model": self.get_model(model),
            "messages": conv_messages,
            "max_tokens": max_tokens or self.config.get("max_tokens", 4096),
        }

        if system:
            params["system"] = system
        if temperature is not None:
            params["temperature"] = temperature

        anthropic_tools = self._convert_tools(tools)
        if anthropic_tools:
            params["tools"] = anthropic_tools

        async with client.messages.stream(**params) as stream:
            current_tool_id = None
            current_tool_name = None
            current_tool_input = ""

            async for event in stream:
                if event.type == "content_block_start":
                    block = event.content_block
                    if block.type == "tool_use":
                        current_tool_id = block.id
                        current_tool_name = block.name
                        current_tool_input = ""

                elif event.type == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta":
                        yield {"type": "text_delta", "text": delta.text}
                    elif delta.type == "input_json_delta":
                        current_tool_input += delta.partial_json

                elif event.type == "content_block_stop":
                    if current_tool_id:
                        args = {}
                        try:
                            args = json.loads(current_tool_input) if current_tool_input else {}
                        except json.JSONDecodeError:
                            pass
                        yield {
                            "type": "tool_call",
                            "tool_call_id": current_tool_id,
                            "tool_name": current_tool_name,
                            "args": args,
                        }
                        current_tool_id = None
                        current_tool_name = None
                        current_tool_input = ""

                elif event.type == "message_stop":
                    pass

            # Emit usage from final message
            final = await stream.get_final_message()
            yield {
                "type": "usage",
                "usage": {
                    "prompt_tokens": final.usage.input_tokens,
                    "completion_tokens": final.usage.output_tokens,
                },
            }
