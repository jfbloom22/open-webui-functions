# Tools Development Guide

Tools are functions that AI models can invoke through function calling. Use Tools to give models the ability to perform specific operations like web searches, calculations, or data retrieval.

## When to Use Tools

Use a Tool when you want to:

- Enable model function calling capabilities
- Create utility functions the model can invoke automatically
- Build integrations the model can use on demand
- Provide structured data retrieval
- Perform calculations or data processing
- Access external APIs based on model decisions

## Key Differences from Other Function Types

- **Pipes**: Appear as custom models in the selector
- **Filters**: Modify inputs/outputs for all interactions
- **Actions**: User-triggered buttons on messages
- **Tools**: Model-invoked functions (function calling)

## Basic Structure

```python
"""
title: My Custom Tool
author: Your Name
version: 1.0.0
required_open_webui_version: 0.4.0
requirements: requests
description: Tool description for the model to understand when to use it
"""

from pydantic import BaseModel, Field
from typing import Any, Callable

class Tools:
    class Valves(BaseModel):
        API_KEY: str = Field(
            default="",
            description="API key for the service"
        )
    
    def __init__(self):
        self.valves = self.Valves()
    
    async def my_function(
        self,
        parameter: str,
        __user__: dict[str, Any] | None = None,
        __event_emitter__: Callable[[dict], Any] | None = None,
    ) -> str:
        """
        Brief description of what this function does.
        
        The model uses this docstring to understand when to call this function.
        
        :param parameter: Description of the parameter
        :return: Description of what is returned
        """
        # Your implementation
        return f"Result: {parameter}"
```

## Critical Requirements

### 1. Complete Type Hints

Type hints are **required** for all parameters and return values. They generate the JSON schema sent to the model.

```python
# Good: Complete type hints
async def search_web(
    self,
    query: str,
    max_results: int = 10,
    __user__: dict | None = None,
) -> list[dict[str, str]]:
    pass

# Bad: Missing or incomplete type hints
async def search_web(self, query, max_results=10):  # Will not work!
    pass
```

### 2. Descriptive Docstrings

Models use docstrings to decide when to call your function:

```python
async def get_weather(
    self,
    location: str,
    units: str = "celsius",
) -> dict[str, Any]:
    """
    Get current weather information for a specific location.
    
    Use this function when the user asks about weather, temperature,
    or current conditions for any city or location.
    
    :param location: City name or location (e.g., "London", "New York")
    :param units: Temperature units, either "celsius" or "fahrenheit"
    :return: Dictionary with temperature, conditions, and forecast
    """
    pass
```

### 3. Nested Type Hints

Provide complete type information for nested structures:

```python
from typing import TypedDict

class SearchResult(TypedDict):
    title: str
    url: str
    snippet: str

async def search(
    self,
    query: str,
) -> list[SearchResult]:
    """Search the web and return results."""
    pass
```

## Modern Tool Authoring Rules

### Metadata and Class Contract

Tools are native Python toolkits. Open WebUI expects a top-level `class Tools` with one or
more typed methods. In Open WebUI itself, a toolkit is a single Python file; in this
repository, keep the existing contribution layout of `tools/<tool_name>/main.py`.

Top-level metadata should include:

- `title`: Display name
- `description`: What it does and example user requests
- `author`: Author name
- `version`: Semantic version
- `license`: License name
- `requirements`: Only pip-installable packages that are truly required

Use `Valves` for admin-managed configuration and `UserValves` for per-user configuration.
Both should inherit from `pydantic.BaseModel` and use `Field(...)` descriptions.

### Reserved Optional Arguments

Open WebUI can inject these arguments into tool methods when declared:

- `__event_emitter__`: Emit status, citation, notification, file, follow-up, and title events
- `__event_call__`: Request user confirmation or input
- `__user__`: User details and `__user__["valves"]`
- `__metadata__`: Chat metadata, including function-calling mode
- `__messages__`: Previous messages
- `__files__`: Attached files
- `__model__`: Model information
- `__oauth_token__`: OAuth token payload for authenticated upstream calls

Only add injected arguments that the method actually needs.

### Event Emitter Compatibility

Use `status` events for progress and always finish with `done: True`:

```python
if __event_emitter__:
    await __event_emitter__({
        "type": "status",
        "data": {
            "description": "Fetching data...",
            "done": False,
            "hidden": False,
        },
    })
```

For native function-calling compatibility, prefer these event types:

- `status`
- `citation`
- `notification`
- `files`
- `chat:title`
- `chat:message:follow_ups`

Avoid `message`, `chat:message:delta`, `chat:message`, and `replace` from Tools when native
function-calling mode may be used. Native completion snapshots can overwrite those updates.

When emitting custom citations, set `self.citation = False` in `__init__` so automatic
citations do not replace your custom events:

```python
class Tools:
    def __init__(self):
        self.valves = self.Valves()
        self.citation = False
```

### Rich HTML Cards

Return `HTMLResponse` when a tool should render an inline UI card in chat:

```python
from fastapi.responses import HTMLResponse

return HTMLResponse(
    content=html_content,
    headers={"Content-Disposition": "inline"},
)
```

HTML card conventions:

- Use `html, body { background: transparent; }` because the card runs in a chat iframe
- Use inline CSS and inline scripts; avoid external assets unless necessary
- Keep card content responsive and readable around 600-800px max width
- Escape all user/API content before embedding it into HTML
- Include a height reporter so the iframe resizes with content

```html
<script>
function reportHeight() {
    const height = document.documentElement.scrollHeight;
    parent.postMessage({type: "iframe:height", height}, "*");
}
window.addEventListener("load", reportHeight);
if (typeof ResizeObserver !== "undefined") {
    new ResizeObserver(reportHeight).observe(document.body);
}
</script>
```

### HTTP and Runtime Conventions

- Prefer `httpx.AsyncClient` or `aiohttp` for new async HTTP work
- Always set a `User-Agent`, timeout, and `raise_for_status()` equivalent
- Return actionable error strings or typed error objects
- Avoid adding dependencies unless they clearly reduce complexity
- For production deployments with multiple workers, preinstall frontmatter requirements and consider `ENABLE_PIP_INSTALL_FRONTMATTER_REQUIREMENTS=False`

### Python Version Compatibility

Open WebUI deployments commonly run Python 3.10/3.11. Avoid Python 3.12-only syntax.
For complex f-strings, precompute dict/list access first so quoting stays unambiguous:

```python
name = data["name"]
last_price = prices[-1]
return f"{name}: ${last_price}"
```

## Complete Web Search Tool Example

```python
"""
title: Web Search Tool
author: Open WebUI Team
version: 1.0.0
required_open_webui_version: 0.4.0
requirements: aiohttp, beautifulsoup4
description: Search the web and retrieve relevant information
"""

from pydantic import BaseModel, Field
from typing import Any, Callable, TypedDict
import aiohttp
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

class SearchResult(TypedDict):
    """Single search result structure."""
    title: str
    url: str
    snippet: str

class Tools:
    class Valves(BaseModel):
        SEARCH_API_KEY: str = Field(
            default="",
            description="API key for search service"
        )
        SEARCH_API_URL: str = Field(
            default="https://api.search.com/v1",
            description="Search API base URL"
        )
        MAX_RESULTS: int = Field(
            default=10,
            ge=1,
            le=50,
            description="Maximum number of search results to return"
        )
        TIMEOUT: int = Field(
            default=30,
            ge=5,
            le=120,
            description="Request timeout in seconds"
        )
    
    def __init__(self):
        self.valves = self.Valves()
    
    async def search_web(
        self,
        query: str,
        num_results: int = 5,
        __user__: dict[str, Any] | None = None,
        __event_emitter__: Callable[[dict], Any] | None = None,
    ) -> list[SearchResult]:
        """
        Search the web for information.
        
        Use this function when you need to find current information,
        look up facts, or search for content on the internet.
        
        :param query: Search query string
        :param num_results: Number of results to return (1-50)
        :return: List of search results with title, URL, and snippet
        """
        
        # Validate API key
        if not self.valves.SEARCH_API_KEY:
            logger.error("Search API key not configured")
            return []
        
        # Limit results
        num_results = min(num_results, self.valves.MAX_RESULTS)
        
        # Send status update
        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {
                    "description": f"Searching for: {query}",
                    "done": False
                }
            })
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.valves.SEARCH_API_URL}/search",
                    params={
                        "q": query,
                        "num": num_results,
                    },
                    headers={
                        "Authorization": f"Bearer {self.valves.SEARCH_API_KEY}",
                    },
                    timeout=self.valves.TIMEOUT,
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
                    # Parse results
                    results: list[SearchResult] = []
                    
                    for item in data.get("results", []):
                        results.append({
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "snippet": item.get("snippet", ""),
                        })
                    
                    # Success notification
                    if __event_emitter__:
                        await __event_emitter__({
                            "type": "status",
                            "data": {
                                "description": f"Found {len(results)} results",
                                "done": True
                            }
                        })
                    
                    logger.info(f"Search completed: {query} -> {len(results)} results")
                    
                    return results
        
        except aiohttp.ClientResponseError as e:
            logger.error(f"Search API error: {e}")
            
            if __event_emitter__:
                await __event_emitter__({
                    "type": "notification",
                    "data": {
                        "type": "error",
                        "content": f"Search failed: {e.message}"
                    }
                })
            
            return []
        
        except Exception as e:
            logger.exception("Search failed")
            
            if __event_emitter__:
                await __event_emitter__({
                    "type": "notification",
                    "data": {
                        "type": "error",
                        "content": f"Search error: {str(e)}"
                    }
                })
            
            return []
    
    async def scrape_webpage(
        self,
        url: str,
        __event_emitter__: Callable | None = None,
    ) -> str:
        """
        Fetch and extract text content from a webpage.
        
        Use this function when you need to read the content of a specific
        webpage or URL.
        
        :param url: URL of the webpage to scrape
        :return: Extracted text content from the webpage
        """
        
        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {
                    "description": f"Fetching: {url}",
                    "done": False
                }
            })
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=self.valves.TIMEOUT,
                ) as response:
                    response.raise_for_status()
                    html = await response.text()
                    
                    # Parse with BeautifulSoup
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Remove script and style elements
                    for script in soup(["script", "style"]):
                        script.decompose()
                    
                    # Get text
                    text = soup.get_text()
                    
                    # Clean up whitespace
                    lines = (line.strip() for line in text.splitlines())
                    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                    text = '\n'.join(chunk for chunk in chunks if chunk)
                    
                    # Limit length
                    max_length = 5000
                    if len(text) > max_length:
                        text = text[:max_length] + "..."
                    
                    if __event_emitter__:
                        await __event_emitter__({
                            "type": "status",
                            "data": {
                                "description": "Content extracted",
                                "done": True
                            }
                        })
                    
                    return text
        
        except Exception as e:
            logger.error(f"Scraping failed: {e}")
            
            if __event_emitter__:
                await __event_emitter__({
                    "type": "notification",
                    "data": {
                        "type": "error",
                        "content": f"Failed to fetch webpage: {str(e)}"
                    }
                })
            
            return f"Error: Could not fetch content from {url}"
```

## Multiple Tools in One Class

Define multiple tool functions in a single class:

```python
class Tools:
    def __init__(self):
        self.valves = self.Valves()
    
    async def calculate_sum(self, a: float, b: float) -> float:
        """Add two numbers together."""
        return a + b
    
    async def calculate_product(self, a: float, b: float) -> float:
        """Multiply two numbers together."""
        return a * b
    
    async def calculate_factorial(self, n: int) -> int:
        """Calculate factorial of a number."""
        if n < 0:
            raise ValueError("Factorial not defined for negative numbers")
        if n == 0:
            return 1
        result = 1
        for i in range(1, n + 1):
            result *= i
        return result
```

## Complex Parameter Types

### Using Enums

```python
from enum import Enum

class TemperatureUnit(str, Enum):
    CELSIUS = "celsius"
    FAHRENHEIT = "fahrenheit"
    KELVIN = "kelvin"

class Tools:
    async def get_temperature(
        self,
        location: str,
        unit: TemperatureUnit = TemperatureUnit.CELSIUS,
    ) -> dict[str, Any]:
        """
        Get temperature for a location.
        
        :param location: City or location name
        :param unit: Temperature unit (celsius, fahrenheit, or kelvin)
        """
        pass
```

### Using TypedDict for Structured Returns

```python
from typing import TypedDict, Literal

class WeatherData(TypedDict):
    temperature: float
    conditions: str
    humidity: int
    wind_speed: float
    forecast: list[str]

class Tools:
    async def get_weather(
        self,
        location: str,
    ) -> WeatherData:
        """Get detailed weather information."""
        return {
            "temperature": 22.5,
            "conditions": "Partly cloudy",
            "humidity": 65,
            "wind_speed": 10.5,
            "forecast": ["Clear tomorrow", "Rain on Friday"],
        }
```

### Optional Parameters with Defaults

```python
async def search_products(
    self,
    query: str,
    category: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    in_stock_only: bool = True,
) -> list[dict[str, Any]]:
    """
    Search for products with optional filters.
    
    :param query: Search query
    :param category: Product category filter (optional)
    :param min_price: Minimum price filter (optional)
    :param max_price: Maximum price filter (optional)
    :param in_stock_only: Only show in-stock items
    """
    pass
```

## Handling User Context

Access user information in your tools:

```python
async def get_user_preferences(
    self,
    preference_type: str,
    __user__: dict | None = None,
) -> dict[str, Any]:
    """
    Retrieve user-specific preferences.
    
    :param preference_type: Type of preference to retrieve
    """
    if not __user__:
        return {"error": "User not authenticated"}
    
    user_id = __user__["id"]
    
    # Fetch user preferences from database
    preferences = self.fetch_preferences(user_id, preference_type)
    
    return preferences
```

## Error Handling Best Practices

```python
async def risky_operation(
    self,
    parameter: str,
    __event_emitter__: Callable | None = None,
) -> dict[str, Any]:
    """Perform an operation that might fail."""
    
    try:
        # Validate input
        if not parameter:
            return {
                "success": False,
                "error": "Parameter is required"
            }
        
        # Perform operation
        result = await self.perform_operation(parameter)
        
        return {
            "success": True,
            "data": result
        }
    
    except ValueError as e:
        # Specific error handling
        logger.warning(f"Invalid input: {e}")
        return {
            "success": False,
            "error": f"Invalid input: {str(e)}"
        }
    
    except aiohttp.ClientError as e:
        # Network error handling
        logger.error(f"Network error: {e}")
        
        if __event_emitter__:
            await __event_emitter__({
                "type": "notification",
                "data": {
                    "type": "error",
                    "content": "Network error occurred"
                }
            })
        
        return {
            "success": False,
            "error": "Network error"
        }
    
    except Exception as e:
        # Catch-all error handling
        logger.exception("Operation failed")
        
        return {
            "success": False,
            "error": "An unexpected error occurred"
        }
```

## Caching Tool Responses

```python
from functools import lru_cache
import time

class Tools:
    def __init__(self):
        self.valves = self.Valves()
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes
    
    def _get_cached(self, key: str) -> Any | None:
        """Get cached value if not expired."""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self._cache_ttl:
                return value
            del self._cache[key]
        return None
    
    def _set_cache(self, key: str, value: Any):
        """Cache value with timestamp."""
        self._cache[key] = (value, time.time())
    
    async def expensive_lookup(
        self,
        query: str,
    ) -> dict[str, Any]:
        """Perform expensive lookup with caching."""
        
        # Check cache
        cache_key = f"lookup:{query}"
        cached = self._get_cached(cache_key)
        
        if cached is not None:
            return cached
        
        # Perform lookup
        result = await self.perform_lookup(query)
        
        # Cache result
        self._set_cache(cache_key, result)
        
        return result
```

## Rate Limiting

```python
import asyncio
from collections import deque

class RateLimiter:
    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self.calls = deque()
    
    async def acquire(self):
        """Wait if rate limit exceeded."""
        now = time.time()
        
        # Remove old calls
        while self.calls and self.calls[0] < now - self.period:
            self.calls.popleft()
        
        # Wait if needed
        if len(self.calls) >= self.max_calls:
            sleep_time = self.period - (now - self.calls[0])
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        
        self.calls.append(time.time())

class Tools:
    def __init__(self):
        self.valves = self.Valves()
        self._rate_limiter = RateLimiter(max_calls=10, period=60.0)
    
    async def api_call(self, query: str) -> dict:
        """Make rate-limited API call."""
        await self._rate_limiter.acquire()
        
        # Make API call
        return await self.call_api(query)
```

## Testing Tools

### Manual Testing

Test in Open WebUI by asking the model to use your tool:

```
User: "Search for information about Python async programming"

Model decides to call search_web tool:
- query: "Python async programming"
- num_results: 5

Tool returns results, model incorporates into response.
```

### Unit Testing

```python
import pytest

@pytest.mark.asyncio
async def test_search_web():
    tools = Tools()
    tools.valves.SEARCH_API_KEY = "test-key"
    
    results = await tools.search_web("test query")
    
    assert isinstance(results, list)
    if results:
        assert "title" in results[0]
        assert "url" in results[0]

@pytest.mark.asyncio
async def test_search_web_no_api_key():
    tools = Tools()
    tools.valves.SEARCH_API_KEY = ""
    
    results = await tools.search_web("test")
    
    assert results == []
```

## Testing Checklist

- [ ] Tool appears in function calling schema
- [ ] Model can invoke the tool successfully
- [ ] All parameters work as expected
- [ ] Optional parameters have sensible defaults
- [ ] Return values match type hints
- [ ] Error handling works properly
- [ ] Event emitters send updates
- [ ] Native/default function-calling behavior is checked when events are used
- [ ] Custom citations set `self.citation = False`
- [ ] HTML cards use inline content disposition and resize correctly
- [ ] HTTP calls set `User-Agent`, timeout, and status handling
- [ ] User context is accessible
- [ ] Rate limiting works (if implemented)
- [ ] Caching works (if implemented)
- [ ] Performance is acceptable

## Common Pitfalls

1. **Missing type hints** - Required for JSON schema generation
2. **Incomplete type hints** - Nested types must be fully specified
3. **Vague docstrings** - Model won't know when to use your tool
4. **Blocking operations** - Use async for all I/O
5. **No error handling** - Always use try-except
6. **No input validation** - Validate parameters before use
7. **Poor return values** - Return structured, typed data
8. **Forgetting event emitters** - Provide status updates
9. **Native-mode event conflicts** - Avoid message replacement events in native mode
10. **Unsafe HTML cards** - Escape content and use transparent iframe backgrounds
11. **Runtime pip races** - Preinstall requirements in multi-worker deployments

## Best Practices Summary

1. **Complete type hints everywhere** - Parameters and returns
2. **Clear, descriptive docstrings** - Help the model understand usage
3. **Structured return types** - Use TypedDict for complex returns
4. **Comprehensive error handling** - Catch and handle all errors
5. **Input validation** - Validate before processing
6. **Status updates** - Use event emitters for long operations
7. **Async operations** - Use async for all I/O
8. **Caching when appropriate** - Cache expensive operations
9. **Rate limiting** - Protect external APIs
10. **Logging** - Log for debugging and monitoring
11. **Mode-aware events** - Use native-compatible events unless default mode is required
12. **Inline rich UI carefully** - Use `HTMLResponse` cards only when visual output improves the workflow

## Additional Resources

- [Tools Documentation](https://docs.openwebui.com/features/extensibility/plugin/tools/)
- [Events Documentation](https://docs.openwebui.com/features/extensibility/plugin/development/events/)
- [Valves Documentation](https://docs.openwebui.com/features/extensibility/plugin/development/valves/)
- [Example Tools](https://openwebui.com/search?type=tool)
- [Type Hints Guide](https://typing.python.org/en/latest/)
