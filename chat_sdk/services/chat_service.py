"""
ChatService - Core orchestrator for the chat SDK.

Equivalent to Vercel AI SDK's streamText/generateText server-side functions.
Manages the full lifecycle: receive message → middleware → provider → tool loop → persist.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, AsyncGenerator

from django.conf import settings

from ..models import Conversation, Message, Artifact
from .message_converter import MessageConverter
from .tool_registry import ToolRegistry, default_registry

logger = logging.getLogger(__name__)


class StreamEvent:
    """A single event in a streaming response. Matches Vercel's stream part types."""

    def __init__(self, event_type: str, data: dict[str, Any] | None = None):
        self.type = event_type
        self.data = data or {}

    def to_dict(self) -> dict:
        return {"type": self.type, **self.data}

    @staticmethod
    def stream_start(message_id: str) -> "StreamEvent":
        return StreamEvent("stream_start", {"message_id": message_id})

    @staticmethod
    def text_delta(text: str) -> "StreamEvent":
        return StreamEvent("text_delta", {"text": text})

    @staticmethod
    def tool_call_start(tool_call_id: str, tool_name: str) -> "StreamEvent":
        return StreamEvent("tool_call_start", {
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
        })

    @staticmethod
    def tool_input_delta(tool_call_id: str, input_delta: str) -> "StreamEvent":
        return StreamEvent("tool_input_delta", {
            "tool_call_id": tool_call_id,
            "input_delta": input_delta,
        })

    @staticmethod
    def tool_input_ready(tool_call_id: str, tool_input: dict) -> "StreamEvent":
        return StreamEvent("tool_input_ready", {
            "tool_call_id": tool_call_id,
            "input": tool_input,
        })

    @staticmethod
    def tool_output(tool_call_id: str, output: Any) -> "StreamEvent":
        return StreamEvent("tool_output", {
            "tool_call_id": tool_call_id,
            "output": output,
        })

    @staticmethod
    def step_start(step: int) -> "StreamEvent":
        return StreamEvent("step_start", {"step": step})

    @staticmethod
    def step_finish(step: int, finish_reason: str, usage: dict | None = None) -> "StreamEvent":
        return StreamEvent("step_finish", {
            "step": step,
            "finish_reason": finish_reason,
            "usage": usage or {},
        })

    @staticmethod
    def stream_end(finish_reason: str = "stop", usage: dict | None = None) -> "StreamEvent":
        return StreamEvent("stream_end", {
            "finish_reason": finish_reason,
            "usage": usage or {},
        })

    @staticmethod
    def error(message: str) -> "StreamEvent":
        return StreamEvent("error", {"message": message})


def _get_sdk_config() -> dict:
    return getattr(settings, "CHAT_SDK", {})


class ChatService:
    """
    Core chat service. Orchestrates the full chat pipeline.

    Usage:
        service = ChatService()
        async for event in service.stream_message(conversation, "Hello!"):
            await consumer.send_json(event.to_dict())
    """

    def __init__(
        self,
        provider=None,
        tool_registry: ToolRegistry | None = None,
        middleware_pipeline=None,
    ):
        self._provider = provider
        self._tool_registry = tool_registry or default_registry
        self._middleware_pipeline = middleware_pipeline
        self._config = _get_sdk_config()

    @property
    def provider(self):
        if self._provider is None:
            from ..providers.registry import provider_registry
            default = self._config.get("DEFAULT_PROVIDER", "azure_openai")
            default_model = self._config.get("DEFAULT_MODEL", "gpt-4o")
            self._provider = provider_registry.get_provider(default, default_model)
        return self._provider

    @property
    def middleware_pipeline(self):
        if self._middleware_pipeline is None:
            from ..middleware.pipeline import MiddlewarePipeline
            self._middleware_pipeline = MiddlewarePipeline.from_settings()
        return self._middleware_pipeline

    async def stream_message(
        self,
        conversation: Conversation,
        user_text: str,
        attachments: list[dict] | None = None,
        model_id: str | None = None,
        system_prompt: str | None = None,
        max_steps: int | None = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Process a user message and stream the assistant's response.

        This is the main entry point - equivalent to Vercel's streamText().

        Args:
            conversation: The conversation to add the message to
            user_text: The user's message text
            attachments: Optional file attachments
            model_id: Override the conversation's model
            system_prompt: Override the conversation's system prompt
            max_steps: Max tool calling iterations (default from config)

        Yields:
            StreamEvent objects for each streaming update
        """
        max_steps = max_steps or self._config.get("MAX_TOOL_STEPS", 10)
        message_id = str(uuid.uuid4())

        # 1. Persist user message
        user_message = await self._save_user_message(
            conversation, user_text, attachments
        )

        # 2. Signal stream start
        yield StreamEvent.stream_start(message_id)

        try:
            # 3. Build model messages from conversation history
            messages = await self._get_model_messages(conversation, system_prompt)

            # 4. Run middleware transform_params
            params = {
                "messages": messages,
                "model_id": model_id or conversation.model_id,
                "tools": self._tool_registry.to_openai_tools() if self._tool_registry.has_tools() else None,
            }
            params = await self.middleware_pipeline.transform_params(params)

            # 5. Agent loop (tool calling)
            step = 0
            accumulated_text = ""
            accumulated_parts = []
            total_usage = {"prompt_tokens": 0, "completion_tokens": 0}

            while step < max_steps:
                yield StreamEvent.step_start(step)

                # 6. Stream from provider
                step_text = ""
                tool_calls = []
                step_usage = {}

                async for chunk in self._stream_with_middleware(params):
                    if chunk.get("type") == "text_delta":
                        delta = chunk.get("text", "")
                        step_text += delta
                        yield StreamEvent.text_delta(delta)

                    elif chunk.get("type") == "tool_call":
                        tool_calls.append(chunk)
                        yield StreamEvent.tool_call_start(
                            chunk.get("tool_call_id", ""),
                            chunk.get("tool_name", ""),
                        )
                        yield StreamEvent.tool_input_ready(
                            chunk.get("tool_call_id", ""),
                            chunk.get("args", {}),
                        )

                    elif chunk.get("type") == "usage":
                        step_usage = chunk.get("usage", {})
                        total_usage["prompt_tokens"] += step_usage.get("prompt_tokens", 0)
                        total_usage["completion_tokens"] += step_usage.get("completion_tokens", 0)

                accumulated_text += step_text

                # Record text part if any
                if step_text:
                    accumulated_parts.append({"type": "text", "text": step_text})

                # 7. Execute tool calls if any
                if tool_calls and step < max_steps - 1:
                    for tc in tool_calls:
                        tool_name = tc.get("tool_name", "")
                        args = tc.get("args", {})
                        tool_call_id = tc.get("tool_call_id", "")

                        accumulated_parts.append({
                            "type": "tool_call",
                            "tool_call_id": tool_call_id,
                            "tool_name": tool_name,
                            "args": args,
                        })

                        # Execute tool
                        result = await self._tool_registry.execute(tool_name, args)
                        yield StreamEvent.tool_output(tool_call_id, result)

                        accumulated_parts.append({
                            "type": "tool_result",
                            "tool_call_id": tool_call_id,
                            "tool_name": tool_name,
                            "result": result,
                        })

                    # Re-build messages with tool results for next iteration
                    params["messages"] = await self._get_model_messages(
                        conversation, system_prompt, extra_parts=accumulated_parts
                    )

                    yield StreamEvent.step_finish(step, "tool_calls", step_usage)
                    step += 1
                    continue

                # No tool calls - we're done
                yield StreamEvent.step_finish(step, "stop", step_usage)
                break

            # 8. Persist assistant message
            await self._save_assistant_message(
                conversation, accumulated_parts, total_usage, message_id
            )

            # 9. Signal stream end
            yield StreamEvent.stream_end("stop", total_usage)

        except Exception as e:
            logger.exception(f"Stream error in conversation {conversation.id}")
            yield StreamEvent.error(str(e))

    async def generate_message(
        self,
        conversation: Conversation,
        user_text: str,
        **kwargs,
    ) -> Message:
        """
        Non-streaming message generation. Equivalent to Vercel's generateText().

        Collects all stream events and returns the final message.
        """
        full_text = ""
        parts = []

        async for event in self.stream_message(conversation, user_text, **kwargs):
            if event.type == "text_delta":
                full_text += event.data.get("text", "")
            elif event.type == "error":
                raise RuntimeError(event.data.get("message", "Unknown error"))

        # Return the last assistant message
        return await self._get_last_assistant_message(conversation)

    async def generate_title(self, conversation: Conversation) -> str:
        """Auto-generate a conversation title from the first messages."""
        messages = conversation.messages.order_by("created_at")[:4]
        if not messages:
            return "New Conversation"

        text_parts = []
        for msg in messages:
            text_parts.append(f"{msg.role}: {msg.get_text_content()[:100]}")

        prompt = (
            "Generate a short title (max 6 words) for this conversation. "
            "Return only the title, nothing else.\n\n" + "\n".join(text_parts)
        )

        from ..providers.registry import provider_registry
        provider = provider_registry.get_default_provider()

        result = await provider.generate(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=30,
        )
        title = result.get("content", "New Conversation").strip().strip('"')
        conversation.title = title[:255]
        await conversation.asave(update_fields=["title"])
        return title

    # --- Private helpers ---

    async def _save_user_message(
        self, conversation: Conversation, text: str, attachments: list | None
    ) -> Message:
        from channels.db import database_sync_to_async

        @database_sync_to_async
        def _create():
            return Message.objects.create(
                conversation=conversation,
                role=Message.Role.USER,
                parts=[{"type": "text", "text": text}],
                attachments=attachments or [],
            )

        msg = await _create()
        return msg

    async def _save_assistant_message(
        self, conversation: Conversation, parts: list, usage: dict, message_id: str
    ) -> Message:
        from channels.db import database_sync_to_async

        @database_sync_to_async
        def _create():
            return Message.objects.create(
                id=message_id,
                conversation=conversation,
                role=Message.Role.ASSISTANT,
                parts=parts,
                metadata={"usage": usage},
            )

        return await _create()

    async def _get_model_messages(
        self,
        conversation: Conversation,
        system_prompt: str | None = None,
        extra_parts: list | None = None,
    ) -> list[dict]:
        from channels.db import database_sync_to_async

        @database_sync_to_async
        def _build():
            messages = list(conversation.messages.order_by("created_at"))
            model_msgs = MessageConverter.to_model_messages(messages)

            # Prepend system prompt
            sys_prompt = system_prompt or conversation.system_prompt
            if sys_prompt:
                model_msgs.insert(0, {"role": "system", "content": sys_prompt})

            # Append extra parts from current step (tool calls/results)
            if extra_parts:
                assistant_parts = {"role": "assistant", "parts": extra_parts}
                extra_msgs = MessageConverter.to_model_messages([type("Msg", (), {
                    "role": "assistant",
                    "parts": extra_parts,
                    "attachments": [],
                })()])
                model_msgs.extend(extra_msgs)

            return model_msgs

        return await _build()

    async def _get_last_assistant_message(self, conversation: Conversation) -> Message:
        from channels.db import database_sync_to_async

        @database_sync_to_async
        def _get():
            return conversation.messages.filter(
                role=Message.Role.ASSISTANT
            ).order_by("-created_at").first()

        return await _get()

    async def _stream_with_middleware(self, params: dict) -> AsyncGenerator[dict, None]:
        """Stream from provider, wrapped by middleware pipeline."""
        raw_stream = self.provider.stream(
            messages=params["messages"],
            model=params.get("model_id"),
            tools=params.get("tools"),
        )

        wrapped = await self.middleware_pipeline.wrap_stream(raw_stream, params)

        async for chunk in wrapped:
            yield chunk
