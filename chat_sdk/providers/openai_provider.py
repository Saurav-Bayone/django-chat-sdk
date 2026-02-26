"""
OpenAI provider adapter.

Equivalent to Vercel AI SDK's @ai-sdk/openai package.
Uses the official openai Python SDK.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator

from .base import BaseProvider, GenerateResult

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider):
    """
    OpenAI provider using the official Python SDK.

    Config:
        api_key: OpenAI API key
        organization: Optional organization ID
        base_url: Optional custom base URL
    """

    provider_name = "openai"

    def __init__(self, model_id: str = "gpt-4o", **config):
        super().__init__(model_id=model_id, **config)
        self._client = None
        self._async_client = None

    def _get_client(self):
        if self._async_client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError:
                raise ImportError("openai package required: pip install openai")

            self._async_client = AsyncOpenAI(
                api_key=self.config.get("api_key"),
                organization=self.config.get("organization"),
                base_url=self.config.get("base_url"),
            )
        return self._async_client

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
        params = self._build_params(messages, model, tools, max_tokens, temperature, **kwargs)

        response = await client.chat.completions.create(**params)
        choice = response.choices[0]

        tool_calls = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls.append({
                    "tool_call_id": tc.id,
                    "tool_name": tc.function.name,
                    "args": json.loads(tc.function.arguments) if tc.function.arguments else {},
                })

        return GenerateResult(
            content=choice.message.content or "",
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
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
        params = self._build_params(messages, model, tools, max_tokens, temperature, **kwargs)
        params["stream"] = True
        params["stream_options"] = {"include_usage": True}

        response = await client.chat.completions.create(**params)

        current_tool_calls: dict[int, dict] = {}

        async for chunk in response:
            if not chunk.choices and chunk.usage:
                yield {
                    "type": "usage",
                    "usage": {
                        "prompt_tokens": chunk.usage.prompt_tokens,
                        "completion_tokens": chunk.usage.completion_tokens,
                    },
                }
                continue

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            # Text content
            if delta.content:
                yield {"type": "text_delta", "text": delta.content}

            # Tool calls
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index

                    if idx not in current_tool_calls:
                        current_tool_calls[idx] = {
                            "tool_call_id": tc_delta.id or "",
                            "tool_name": "",
                            "args_str": "",
                        }

                    if tc_delta.id:
                        current_tool_calls[idx]["tool_call_id"] = tc_delta.id

                    if tc_delta.function:
                        if tc_delta.function.name:
                            current_tool_calls[idx]["tool_name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            current_tool_calls[idx]["args_str"] += tc_delta.function.arguments

            # Finish reason
            if chunk.choices[0].finish_reason:
                finish = chunk.choices[0].finish_reason

                # Emit completed tool calls
                if finish == "tool_calls":
                    for tc in current_tool_calls.values():
                        args = {}
                        try:
                            args = json.loads(tc["args_str"])
                        except json.JSONDecodeError:
                            pass
                        yield {
                            "type": "tool_call",
                            "tool_call_id": tc["tool_call_id"],
                            "tool_name": tc["tool_name"],
                            "args": args,
                        }
                    current_tool_calls.clear()

    def _build_params(
        self,
        messages: list[dict],
        model: str | None,
        tools: list[dict] | None,
        max_tokens: int | None,
        temperature: float | None,
        **kwargs,
    ) -> dict:
        params = {
            "model": self.get_model(model),
            "messages": messages,
        }
        if tools:
            params["tools"] = tools
        if max_tokens:
            params["max_tokens"] = max_tokens
        if temperature is not None:
            params["temperature"] = temperature
        params.update(kwargs)
        return params
