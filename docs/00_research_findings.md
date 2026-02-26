# Vercel AI Chat SDK - Research Findings

**Date:** 2026-02-25
**Purpose:** Analysis of Vercel AI Chat SDK to inform Django equivalent implementation

## Executive Summary

The Vercel AI SDK (https://github.com/vercel/ai) is a monorepo with 70+ packages organized
into four layers: Core, UI, Providers, and RSC. It provides a unified interface for
interacting with multiple AI providers through streaming text generation, tool calling,
structured output, and agent loops.

The reference chatbot (https://github.com/vercel/chatbot) is a Next.js App Router app
using Drizzle ORM + PostgreSQL, NextAuth.js, and SSE-based streaming.

## Key Concepts We're Adapting

### 1. Provider Adapter Pattern
- All providers implement `LanguageModelV3` interface with `doGenerate()` and `doStream()`
- Unified interface means same code works with any provider
- `@ai-sdk/openai-compatible` base enables rapid integration of OpenAI-compatible APIs
- Provider Registry allows string-based model references

**Our Django equivalent:** Abstract `BaseProvider` class with `generate()` and `stream()`
methods. Leverages existing TalentAI `UnifiedProcessor` patterns.

### 2. Streaming Protocol (SSE)
- Uses Server-Sent Events with JSON payloads
- Stream parts: `start`, `text-delta`, `tool-call-start`, `tool-input-delta`,
  `tool-output-available`, `step-finish`, `finish`, `error`
- Header: `x-vercel-ai-ui-message-stream: v1`

**Our Django equivalent:** Django Channels WebSocket for primary transport (already in use),
with SSE fallback via StreamingHttpResponse for simpler deployments.

### 3. Message Architecture (UIMessage vs ModelMessage)
- `UIMessage`: Rich client-side state with `parts[]` array (text, tool calls, images)
- `ModelMessage`: Stripped-down format for LLM consumption
- `convertToModelMessages()` transforms between them

**Our Django equivalent:** Django model stores UIMessage-equivalent JSON. Service layer
converts to provider-specific format before sending to LLM.

### 4. Middleware System
- Three hooks: `transformParams`, `wrapGenerate`, `wrapStream`
- Use cases: caching, logging, guardrails, RAG injection, cost tracking
- Composable and shareable

**Our Django equivalent:** Python middleware classes with `before_generate()`,
`after_generate()`, `wrap_stream()` methods. Decoratable and chainable.

### 5. Tool Calling
- Tools defined with schema (Zod) + execute function
- Multi-step loops: LLM calls tool → result injected → LLM called again
- Agent abstraction (`ToolLoopAgent`) for production use

**Our Django equivalent:** Tool registry with Pydantic schema validation + callable
execute functions. Celery for long-running tools.

### 6. Database Schema
```
User → Chat (1:N) → Message_v2 (1:N) → Vote_v2 (1:1 per message)
User → Document (1:N) → Suggestion (1:N)
```
Messages store `parts` (JSON) and `attachments` (JSON).

**Our Django equivalent:** Direct Django model mapping with JSONField for parts/attachments.

### 7. UI Components
- Chat, Message, MultimodalInput, ChatHeader, Sidebar, Markdown, Artifact, CodeBlock
- Framework-agnostic AbstractChat base
- Smart scrolling, streaming awareness, tool call rendering

**Our Django equivalent:** Phoenix theme templates with HTMX for interactivity.
WebSocket for streaming, OOB swaps for UI updates.

## What We're NOT Implementing (Out of Scope)

- React Server Components (RSC) - not applicable to Django
- Framework-specific hooks (useChat, useCompletion) - replaced by WebSocket/HTMX
- Vercel Blob storage - using Django file storage + Azure Blob
- AI Gateway string references - using our own model registry
- Video/speech generation - not needed for chat SDK
- DevTools - can add later

## References

- [AI SDK Documentation](https://ai-sdk.dev/docs/introduction)
- [vercel/ai GitHub](https://github.com/vercel/ai)
- [vercel/chatbot GitHub](https://github.com/vercel/chatbot)
- [AI SDK Stream Protocol](https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol)
- [AI SDK Middleware](https://ai-sdk.dev/docs/ai-sdk-core/middleware)
- [py-ai-datastream (Python SSE)](https://github.com/elementary-data/py-ai-datastream)
