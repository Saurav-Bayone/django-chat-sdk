# Feature Mapping: Vercel AI SDK → Django Chat SDK

## Concept-by-Concept Translation

| Vercel AI SDK Concept | Django Chat SDK Equivalent | Notes |
|----------------------|---------------------------|-------|
| `generateText()` | `ChatService.generate()` | Synchronous, non-streaming |
| `streamText()` | `ChatService.stream()` | Returns async generator |
| `useChat` hook | WebSocket ChatConsumer + HTMX | No React needed |
| `useCompletion` hook | `ChatService.complete()` | Single-turn completion |
| `useObject` hook | `ChatService.generate_object()` | Pydantic schema validation |
| UIMessage | `Message.parts` (JSONField) | Same structure, Django model |
| ModelMessage | Provider-specific format | `MessageConverter.to_model_messages()` |
| LanguageModelV3 | `BaseProvider` ABC | `generate()` + `stream()` |
| Provider Registry | `ProviderRegistry` singleton | String-based lookup |
| `@ai-sdk/openai` | `OpenAIProvider` | Uses `openai` Python SDK |
| `@ai-sdk/anthropic` | `AnthropicProvider` | Uses `anthropic` Python SDK |
| `@ai-sdk/azure` | `AzureOpenAIProvider` | Uses `openai` Python SDK (Azure) |
| `@ai-sdk/openai-compatible` | `OpenAICompatibleProvider` | Base class |
| `tool()` | `@chat_tool` decorator | Pydantic schema + callable |
| `ToolLoopAgent` | `ChatService.agent_loop()` | Max steps, tool calling loop |
| Language Model Middleware | `BaseMiddleware` pipeline | `before/after/wrap_stream` |
| `wrapGenerate` | `middleware.wrap_generate()` | Before/after non-streaming |
| `wrapStream` | `middleware.wrap_stream()` | Wraps async generator |
| `transformParams` | `middleware.transform_params()` | Modify before LLM call |
| ChatStore | Django model + WebSocket state | Per-conversation state |
| SSE Data Stream | WebSocket JSON messages | Same event types |
| `toDataStreamResponse()` | `StreamingHttpResponse` (SSE) | Fallback transport |
| NextAuth.js | Django allauth / session auth | Existing TalentAI auth |
| Drizzle ORM | Django ORM | Native Django models |
| Vercel Blob | Django FileField / Azure Blob | File storage backend |
| shadcn/ui components | Phoenix Bootstrap theme | Cards, modals, badges |
| React state management | HTMX + WebSocket | Server-driven UI |
| `experimental_attachments` | `Message.attachments` JSONField | File references |
| Document/Artifact | `Artifact` model | text/code/image types |
| Suggestion | Future enhancement | Not in initial release |
| Vote | `Vote` model | Upvote/downvote per message |

## Stream Event Types Mapping

| Vercel SSE Event | WebSocket Event | Description |
|-----------------|-----------------|-------------|
| `start` | `{"type": "stream_start"}` | New message beginning |
| `text-delta` | `{"type": "text_delta"}` | Incremental text |
| `tool-call-start` | `{"type": "tool_call_start"}` | Tool invocation begin |
| `tool-input-delta` | `{"type": "tool_input_delta"}` | Tool args streaming |
| `tool-input-available` | `{"type": "tool_input_ready"}` | Tool args complete |
| `tool-output-available` | `{"type": "tool_output"}` | Tool result |
| `step-start` | `{"type": "step_start"}` | LLM call begin |
| `step-finish` | `{"type": "step_finish"}` | LLM call end |
| `finish` | `{"type": "stream_end"}` | Message complete |
| `error` | `{"type": "error"}` | Error occurred |

## UI Component Mapping

| Vercel Component | Phoenix/Django Template | Implementation |
|-----------------|------------------------|----------------|
| `<Chat>` | `chat_interface.html` | Full chat page layout |
| `<Message>` | `message_bubble.html` | Role-aware message card |
| `<MultimodalInput>` | `input_area.html` | Textarea + file upload |
| `<ChatHeader>` | `chat_header.html` | Model selector dropdown |
| `<Sidebar>` | `sidebar.html` | Conversation list + new chat |
| `<Markdown>` | `markdownify` filter | Django Markdownify |
| `<Artifact>` | `artifacts_panel.html` | Offcanvas/side panel |
| `<CodeBlock>` | `highlight` filter | Pygments syntax highlighting |
| `<ConversationContainer>` | `message_list.html` | SimpleBars scrollable area |
| `<ToolCall>` | `tool_result.html` | Collapsible tool display |

## Provider Interface Comparison

### Vercel (TypeScript)
```typescript
interface LanguageModelV3 {
  readonly provider: string;
  readonly modelId: string;
  doGenerate(options): Promise<GenerateResult>;
  doStream(options): Promise<StreamResult>;
}
```

### Django Chat SDK (Python)
```python
class BaseProvider(ABC):
    provider_name: str
    model_id: str

    @abstractmethod
    async def generate(self, messages, **kwargs) -> GenerateResult: ...

    @abstractmethod
    async def stream(self, messages, **kwargs) -> AsyncGenerator[StreamEvent]: ...
```

## Middleware Interface Comparison

### Vercel (TypeScript)
```typescript
const middleware = {
  transformParams: async ({ params }) => modifiedParams,
  wrapGenerate: async ({ doGenerate, params }) => result,
  wrapStream: async ({ doStream, params }) => streamResult,
};
```

### Django Chat SDK (Python)
```python
class BaseMiddleware(ABC):
    async def transform_params(self, params: dict) -> dict: ...
    async def before_generate(self, params: dict) -> None: ...
    async def after_generate(self, params: dict, result) -> None: ...
    async def wrap_stream(self, stream, params: dict) -> AsyncGenerator: ...
```
