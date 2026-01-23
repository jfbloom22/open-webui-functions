# Pipes Development Guide

Pipes are custom models/agents in Open WebUI that appear in the model selector. Use Pipes to create proxy integrations to AI services, build custom agents, or integrate non-AI services.

## When to Use Pipes

Use a Pipe when you want to:

- Proxy requests to external AI services (OpenAI, Anthropic, Google, etc.)
- Create custom agents with specific behaviors
- Combine multiple models or services
- Integrate non-AI services (search engines, home automation, APIs, etc.)
- Build complex workflows that appear as a single "model"

## Basic Structure

```python
"""
title: My Custom Pipe
author: Your Name
version: 1.0.0
required_open_webui_version: 0.4.0
requirements: aiohttp
"""

from pydantic import BaseModel, Field
from typing import Any, Callable
import aiohttp

class Pipe:
    class Valves(BaseModel):
        API_KEY: str = Field(default="", description="API key for service")
        API_URL: str = Field(
            default="https://api.example.com",
            description="Base URL for API"
        )
    
    def __init__(self):
        self.valves = self.Valves()
    
    async def pipe(
        self,
        body: dict[str, Any],
        __user__: dict[str, Any] | None = None,
        __event_emitter__: Callable[[dict], Any] | None = None,
    ) -> dict[str, Any] | str:
        """
        Main processing function.
        
        Args:
            body: Request body containing messages and model info
            __user__: User information
            __event_emitter__: Function for sending status updates
        
        Returns:
            Response from the model/service
        """
        # Your implementation here
        pass
```

## Creating Multiple Models (Manifold Pattern)

Use the `pipes()` function to expose multiple models:

```python
class Pipe:
    class Valves(BaseModel):
        API_KEY: str = Field(default="")
    
    def __init__(self):
        self.valves = self.Valves()
    
    def pipes(self) -> list[dict[str, str]]:
        """
        Return list of available models.
        
        Returns:
            List of model definitions with id and name
        """
        if not self.valves.API_KEY:
            return [{
                "id": "error",
                "name": "API Key Required - Configure in Valves"
            }]
        
        try:
            # Fetch available models from API
            models = self.fetch_models()
            
            return [
                {
                    "id": model["id"],
                    "name": f"MyService/{model['name']}"
                }
                for model in models
            ]
        except Exception as e:
            return [{
                "id": "error",
                "name": f"Error: {str(e)}"
            }]
    
    async def pipe(self, body: dict, __user__=None, __event_emitter__=None):
        """Process request for selected model."""
        model_id = body["model"]  # Selected model ID
        # Process with specific model
        pass
```

## Handling Streaming Responses

Pipes must support both streaming and non-streaming responses:

```python
async def pipe(self, body: dict, __event_emitter__=None):
    is_streaming = body.get("stream", False)
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url=f"{self.valves.API_URL}/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {self.valves.API_KEY}"},
        ) as response:
            response.raise_for_status()
            
            if is_streaming:
                # Return async iterator for streaming
                return response.content.iter_any()
            else:
                # Return complete response
                return await response.json()
```

## Model ID Extraction

Extract the actual model ID from the full model name:

```python
async def pipe(self, body: dict):
    # Full name format: "provider.model_id"
    # Extract: "model_id"
    
    full_name = body["model"]
    
    if "." in full_name:
        # Split and get model ID part
        model_id = full_name.split(".", 1)[1]
    else:
        model_id = full_name
    
    # Update body with extracted model ID
    payload = {**body, "model": model_id}
    
    # Make API request with correct model ID
    return await self.make_request(payload)
```

## Complete OpenAI Proxy Example

```python
"""
title: OpenAI Proxy Pipe
author: Open WebUI Team
version: 1.0.0
required_open_webui_version: 0.4.0
requirements: aiohttp
"""

from pydantic import BaseModel, Field
from typing import Any, Callable, AsyncIterator
import aiohttp
import logging

logger = logging.getLogger(__name__)

class Pipe:
    class Valves(BaseModel):
        NAME_PREFIX: str = Field(
            default="OpenAI/",
            description="Prefix for model names in the selector"
        )
        API_BASE_URL: str = Field(
            default="https://api.openai.com/v1",
            description="OpenAI API base URL"
        )
        API_KEY: str = Field(
            default="",
            description="OpenAI API key from platform.openai.com"
        )
        TIMEOUT: int = Field(
            default=120,
            ge=1,
            le=300,
            description="Request timeout in seconds"
        )
    
    def __init__(self):
        self.valves = self.Valves()
        self._session: aiohttp.ClientSession | None = None
    
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session with connection pooling."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.valves.TIMEOUT)
            connector = aiohttp.TCPConnector(limit=100, limit_per_host=30)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector
            )
        return self._session
    
    def pipes(self) -> list[dict[str, str]]:
        """Fetch available OpenAI models."""
        if not self.valves.API_KEY:
            return [{
                "id": "error",
                "name": "⚠️ API Key Required"
            }]
        
        try:
            import requests
            
            response = requests.get(
                f"{self.valves.API_BASE_URL}/models",
                headers={"Authorization": f"Bearer {self.valves.API_KEY}"},
                timeout=10
            )
            response.raise_for_status()
            
            models = response.json()
            
            # Filter for GPT models
            return [
                {
                    "id": model["id"],
                    "name": f"{self.valves.NAME_PREFIX}{model.get('id')}"
                }
                for model in models.get("data", [])
                if "gpt" in model["id"]
            ]
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch models: {e}")
            return [{
                "id": "error",
                "name": f"⚠️ Error: {str(e)}"
            }]
    
    async def pipe(
        self,
        body: dict[str, Any],
        __user__: dict[str, Any] | None = None,
        __event_emitter__: Callable[[dict], Any] | None = None,
    ) -> AsyncIterator[bytes] | dict[str, Any]:
        """
        Process chat completion request.
        
        Supports both streaming and non-streaming responses.
        """
        try:
            # Extract model ID
            model_id = body["model"]
            if "." in model_id:
                model_id = model_id.split(".", 1)[1]
            
            # Prepare request
            payload = {**body, "model": model_id}
            
            session = await self.get_session()
            
            # Send status update
            if __event_emitter__:
                await __event_emitter__({
                    "type": "status",
                    "data": {
                        "description": f"Requesting {model_id}...",
                        "done": False
                    }
                })
            
            # Make API request
            async with session.post(
                f"{self.valves.API_BASE_URL}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.valves.API_KEY}",
                    "Content-Type": "application/json"
                }
            ) as response:
                response.raise_for_status()
                
                if body.get("stream", False):
                    # Stream response
                    return response.content.iter_any()
                else:
                    # Complete response
                    result = await response.json()
                    
                    if __event_emitter__:
                        await __event_emitter__({
                            "type": "status",
                            "data": {"description": "Complete", "done": True}
                        })
                    
                    return result
        
        except aiohttp.ClientResponseError as e:
            error_msg = f"API error ({e.status}): {e.message}"
            logger.error(error_msg)
            
        except aiohttp.ClientError as e:
            error_msg = f"Connection error: {str(e)}"
            logger.error(error_msg)
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.exception("Pipe processing failed")
        
        # Send error notification
        if __event_emitter__:
            await __event_emitter__({
                "type": "notification",
                "data": {"type": "error", "content": error_msg}
            })
        
        return {"content": f"Error: {error_msg}"}
```

## Using Internal Open WebUI Functions

Access Open WebUI's internal functions for advanced use cases:

```python
from fastapi import Request
from open_webui.models.users import Users
from open_webui.utils.chat import generate_chat_completion

class Pipe:
    def __init__(self):
        self.valves = self.Valves()
    
    async def pipe(
        self,
        body: dict,
        __user__: dict,
        __request__: Request,
    ) -> str:
        """Use internal Open WebUI chat completion."""
        # Get full user object
        user = Users.get_user_by_id(__user__["id"])
        
        # Specify internal model
        body["model"] = "llama3.2:latest"
        
        # Use internal chat completion
        return await generate_chat_completion(__request__, body, user)
```

## Error Handling Patterns

### Network Errors

```python
import asyncio

try:
    async with session.post(url, json=payload) as response:
        response.raise_for_status()
        return await response.json()
        
except asyncio.TimeoutError:
    return {"content": "Request timed out. Please try again."}
    
except aiohttp.ClientResponseError as e:
    if e.status == 401:
        return {"content": "Authentication failed. Check your API key."}
    elif e.status == 429:
        return {"content": "Rate limit exceeded. Please wait and try again."}
    elif e.status >= 500:
        return {"content": f"Service error ({e.status}). Please try again later."}
    else:
        return {"content": f"Request failed ({e.status}): {e.message}"}
        
except aiohttp.ClientError as e:
    return {"content": f"Connection error: {str(e)}"}
```

### Retry Logic with Exponential Backoff

```python
async def make_request_with_retry(
    self,
    url: str,
    payload: dict,
    max_retries: int = 3
) -> dict:
    """Make HTTP request with retry logic."""
    session = await self.get_session()
    
    for attempt in range(max_retries):
        try:
            async with session.post(url, json=payload) as response:
                # Return on success or client error (don't retry)
                if response.status < 500:
                    response.raise_for_status()
                    return await response.json()
                
                # Server error - retry with backoff
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    await asyncio.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                
        except aiohttp.ClientError as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)
    
    raise RuntimeError(f"Failed after {max_retries} attempts")
```

## Performance Optimization

### Session Management

```python
class Pipe:
    def __init__(self):
        self.valves = self.Valves()
        self._session: aiohttp.ClientSession | None = None
    
    async def get_session(self) -> aiohttp.ClientSession:
        """Reuse session for connection pooling."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=100,  # Total connections
                limit_per_host=30,  # Per-host connections
                ttl_dns_cache=300  # DNS cache TTL
            )
            timeout = aiohttp.ClientTimeout(total=self.valves.TIMEOUT)
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout
            )
        return self._session
    
    async def __del__(self):
        """Clean up session on deletion."""
        if self._session and not self._session.closed:
            await self._session.close()
```

### Response Caching

```python
import time
from typing import Any

class ResponseCache:
    def __init__(self, ttl: int = 300):
        self._cache: dict[str, tuple[Any, float]] = {}
        self.ttl = ttl
    
    def get(self, key: str) -> Any | None:
        """Get cached value if not expired."""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            del self._cache[key]
        return None
    
    def set(self, key: str, value: Any):
        """Cache value with timestamp."""
        self._cache[key] = (value, time.time())
    
    def clear(self):
        """Clear all cached values."""
        self._cache.clear()

class Pipe:
    def __init__(self):
        self.valves = self.Valves()
        self._cache = ResponseCache(ttl=300)  # 5 minute cache
```

## Testing Checklist

- [ ] Pipe appears in model selector
- [ ] Model name displays correctly
- [ ] Streaming responses work
- [ ] Non-streaming responses work
- [ ] Error messages are helpful
- [ ] API key validation works
- [ ] Timeout handling works
- [ ] Multiple models work (if using manifold)
- [ ] Model ID extraction is correct
- [ ] Event emitters send updates
- [ ] Session cleanup happens properly
- [ ] Concurrent requests work

## Common Pitfalls

1. **Forgetting to extract model ID** - Always parse the full model name
2. **Not handling streaming** - Support both streaming and non-streaming
3. **Hardcoding API keys** - Use Valves for configuration
4. **Blocking operations** - Use async for all I/O
5. **No error handling** - Always use try-except blocks
6. **Missing status updates** - Use event emitters for feedback
7. **Session leaks** - Reuse sessions with proper cleanup
8. **No timeout** - Always set request timeouts

## Additional Resources

- [Pipe Function Documentation](https://docs.openwebui.com/features/plugin/functions/pipe)
- [Example Pipes](https://openwebui.com/search?type=pipe)
- [Open WebUI GitHub](https://github.com/open-webui/open-webui)
