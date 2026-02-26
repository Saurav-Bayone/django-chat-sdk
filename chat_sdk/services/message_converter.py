"""
Message format converter: UIMessage (DB) ↔ ModelMessage (LLM API).

Equivalent to Vercel AI SDK's convertToModelMessages().

UIMessage format (stored in DB):
    parts: [{"type": "text", "text": "..."}, {"type": "tool_call", ...}]

ModelMessage format (sent to LLM):
    {"role": "user", "content": "..."} or
    {"role": "assistant", "content": "...", "tool_calls": [...]}
"""

from __future__ import annotations

import json
from typing import Any


class MessageConverter:
    """Converts between UIMessage (parts-based) and ModelMessage (API-ready) formats."""

    @staticmethod
    def to_model_messages(messages) -> list[dict[str, Any]]:
        """
        Convert Django Message queryset/list to provider-ready format.

        Args:
            messages: QuerySet or list of Message model instances

        Returns:
            List of dicts in OpenAI-compatible message format
        """
        model_messages = []

        for msg in messages:
            role = msg.role
            parts = msg.parts if isinstance(msg.parts, list) else []

            if role == "system":
                text = MessageConverter._extract_text(parts)
                if text:
                    model_messages.append({"role": "system", "content": text})

            elif role == "user":
                content = MessageConverter._build_user_content(parts, msg.attachments)
                if content:
                    model_messages.append({"role": "user", "content": content})

            elif role == "assistant":
                assistant_msg = MessageConverter._build_assistant_message(parts)
                if assistant_msg:
                    model_messages.append(assistant_msg)

                # Add tool result messages for any tool calls
                tool_results = [p for p in parts if p.get("type") == "tool_result"]
                for result in tool_results:
                    model_messages.append({
                        "role": "tool",
                        "tool_call_id": result.get("tool_call_id", ""),
                        "content": json.dumps(result.get("result", {}))
                        if not isinstance(result.get("result"), str)
                        else result.get("result", ""),
                    })

            elif role == "tool":
                for part in parts:
                    if part.get("type") == "tool_result":
                        result_content = part.get("result", {})
                        model_messages.append({
                            "role": "tool",
                            "tool_call_id": part.get("tool_call_id", ""),
                            "content": json.dumps(result_content)
                            if not isinstance(result_content, str)
                            else result_content,
                        })

        return model_messages

    @staticmethod
    def _extract_text(parts: list[dict]) -> str:
        """Extract plain text from parts array."""
        texts = []
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                texts.append(part.get("text", ""))
            elif isinstance(part, str):
                texts.append(part)
        return "\n".join(texts)

    @staticmethod
    def _build_user_content(parts: list[dict], attachments: list[dict] | None) -> str | list:
        """Build user message content, handling multimodal if attachments present."""
        text = MessageConverter._extract_text(parts)

        if not attachments:
            return text

        # Multimodal: build content array with text + images
        content = []
        if text:
            content.append({"type": "text", "text": text})

        for attachment in attachments:
            content_type = attachment.get("content_type", "")
            if content_type.startswith("image/"):
                content.append({
                    "type": "image_url",
                    "image_url": {"url": attachment.get("url", "")},
                })

        return content if len(content) > 1 else text

    @staticmethod
    def _build_assistant_message(parts: list[dict]) -> dict | None:
        """Build assistant message with optional tool calls."""
        text = MessageConverter._extract_text(parts)
        tool_calls = [p for p in parts if p.get("type") == "tool_call"]

        if not text and not tool_calls:
            return None

        msg = {"role": "assistant"}

        if text:
            msg["content"] = text

        if tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.get("tool_call_id", ""),
                    "type": "function",
                    "function": {
                        "name": tc.get("tool_name", ""),
                        "arguments": json.dumps(tc.get("args", {}))
                        if not isinstance(tc.get("args"), str)
                        else tc.get("args", "{}"),
                    },
                }
                for tc in tool_calls
            ]
            if not text:
                msg["content"] = None

        return msg

    @staticmethod
    def from_model_response(role: str, content: str, tool_calls=None, metadata=None) -> dict:
        """
        Convert an LLM API response back to UIMessage parts format for storage.

        Returns:
            Dict with 'role', 'parts', 'metadata' ready for Message.objects.create()
        """
        parts = []

        if content:
            parts.append({"type": "text", "text": content})

        if tool_calls:
            for tc in tool_calls:
                func = tc.get("function", {}) if isinstance(tc, dict) else {}
                args = func.get("arguments", "{}")
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        pass

                parts.append({
                    "type": "tool_call",
                    "tool_call_id": tc.get("id", "") if isinstance(tc, dict) else "",
                    "tool_name": func.get("name", ""),
                    "args": args,
                })

        return {
            "role": role,
            "parts": parts,
            "metadata": metadata or {},
        }
