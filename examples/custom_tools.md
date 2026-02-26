# Custom Tools Example

## Defining Tools

Tools give the LLM the ability to execute functions during a conversation.
The Chat SDK handles the multi-step loop automatically.

### Basic Tool

```python
# my_app/tools.py
from chat_sdk.services import chat_tool
from pydantic import BaseModel, Field


class SearchParams(BaseModel):
    query: str = Field(description="Search query")
    limit: int = Field(default=5, description="Max results")


@chat_tool(
    name="search_candidates",
    description="Search the candidate database",
    parameters=SearchParams,
)
async def search_candidates(query: str, limit: int = 5):
    from recruitment.candidates.models import Candidate

    candidates = Candidate.objects.filter(
        name__icontains=query
    )[:limit]

    return [
        {"name": c.name, "title": c.current_title, "location": c.location}
        for c in candidates
    ]
```

### Tool with External API

```python
class WeatherParams(BaseModel):
    city: str = Field(description="City name")


@chat_tool(
    name="get_weather",
    description="Get current weather for a city",
    parameters=WeatherParams,
)
async def get_weather(city: str):
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.weatherapi.com/v1/current.json",
            params={"key": "...", "q": city},
        )
        data = resp.json()
        return {
            "temperature": data["current"]["temp_f"],
            "condition": data["current"]["condition"]["text"],
        }
```

### Tool with Database Query

```python
class PipelineParams(BaseModel):
    pipeline_id: int = Field(description="Pipeline ID")


@chat_tool(
    name="get_pipeline_stats",
    description="Get statistics for a recruitment pipeline",
    parameters=PipelineParams,
)
async def get_pipeline_stats(pipeline_id: int):
    from channels.db import database_sync_to_async
    from recruitment.pipelines.models import Pipeline

    @database_sync_to_async
    def _get():
        pipeline = Pipeline.objects.get(id=pipeline_id)
        return {
            "name": pipeline.name,
            "total_candidates": pipeline.candidates.count(),
            "stages": [
                {"name": s.name, "count": s.candidates.count()}
                for s in pipeline.stages.all()
            ],
        }

    return await _get()
```

## Registering Tools

### Option 1: Register in AppConfig.ready()

```python
# my_app/apps.py
from django.apps import AppConfig


class MyAppConfig(AppConfig):
    name = "my_app"

    def ready(self):
        from chat_sdk.services.tool_registry import default_registry
        from .tools import search_candidates, get_weather, get_pipeline_stats

        default_registry.register(search_candidates)
        default_registry.register(get_weather)
        default_registry.register(get_pipeline_stats)
```

### Option 2: Per-Service Registry

```python
from chat_sdk.services import ChatService, ToolRegistry
from .tools import search_candidates

# Create a dedicated registry
recruiting_tools = ToolRegistry()
recruiting_tools.register(search_candidates)

# Use with a specific service
service = ChatService(tool_registry=recruiting_tools)
```

## How the Tool Loop Works

```
1. User: "Find candidates named John in NYC"
2. ChatService sends to LLM with tool definitions
3. LLM returns: tool_call(search_candidates, {query: "John", limit: 5})
4. ChatService executes tool → gets results
5. ChatService sends tool result back to LLM
6. LLM generates: "I found 3 candidates named John..."
7. Response streamed to user
```

The `MAX_TOOL_STEPS` setting (default: 10) limits the loop to prevent infinite cycles.

## Monitoring Tool Execution

Tool calls are visible in the stream events:

```json
{"type": "tool_call_start", "tool_call_id": "call_1", "tool_name": "search_candidates"}
{"type": "tool_input_ready", "tool_call_id": "call_1", "input": {"query": "John"}}
{"type": "tool_output", "tool_call_id": "call_1", "output": [{"name": "John Doe", ...}]}
```

The UI shows tool calls in collapsible cards with the tool name and result.
