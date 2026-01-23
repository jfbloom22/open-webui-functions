# Open WebUI Extension Development Best Practices

This guide outlines best practices for developing high-quality Open WebUI extensions (Pipes, Filters, Actions, and Tools).

## Table of Contents

- [Code Quality](#code-quality)
- [Type Safety](#type-safety)
- [Async Programming](#async-programming)
- [Error Handling](#error-handling)
- [Configuration Management](#configuration-management)
- [Security](#security)
- [Performance](#performance)
- [User Experience](#user-experience)
- [Documentation](#documentation)
- [Testing](#testing)

## Code Quality

### Use Modern Python Syntax

```python
# Good: Modern union syntax (Python 3.10+)
def process(value: str | None) -> list[dict[str, str]]:
    pass

# Avoid: Old-style typing imports
from typing import Optional, List, Dict
def process(value: Optional[str]) -> List[Dict[str, str]]:
    pass
```

### Follow PEP 8 with Modifications

- Maximum line length: 100 characters (not 79)
- Use double quotes for strings
- Use trailing commas in multi-line collections
- Group imports: standard library, third-party, local

```python
# Good
from typing import Any, Callable
import asyncio

from pydantic import BaseModel, Field
import requests

from open_webui.utils.chat import generate_chat_completion
```

### Keep Functions Focused

Each function should do one thing well:

```python
# Good: Single responsibility
async def fetch_data(url: str) -> dict:
    """Fetch data from URL."""
    pass

async def process_data(data: dict) -> str:
    """Process fetched data."""
    pass

# Avoid: Multiple responsibilities
async def fetch_and_process(url: str) -> str:
    """Fetch and process data."""
    # Too much in one function
    pass
```

## Type Safety

### Comprehensive Type Hints

Type hints are **required** for Open WebUI functions. They generate the JSON schema used by models.

```python
from typing import Any, Callable
from pydantic import BaseModel, Field

# Good: Complete type hints
async def action(
    self,
    body: dict[str, Any],
    __user__: dict[str, Any] | None = None,
    __event_emitter__: Callable[[dict], Any] | None = None,
) -> dict[str, Any]:
    pass

# Avoid: Missing type hints
async def action(self, body, __user__=None, __event_emitter__=None):
    pass
```

### Use Pydantic for Validation

```python
from pydantic import BaseModel, Field, validator

class Valves(BaseModel):
    api_key: str = Field(default="", min_length=1)
    timeout: int = Field(default=30, ge=1, le=300)
    retries: int = Field(default=3, ge=0, le=10)
    
    @validator("api_key")
    def validate_api_key(cls, v):
        if v and not v.startswith("sk-"):
            raise ValueError("API key must start with 'sk-'")
        return v
```

### Leverage Annotated Types

```python
from typing import Annotated
from pydantic import Field, AfterValidator

def validate_url(v: str) -> str:
    if not v.startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")
    return v

Url = Annotated[str, AfterValidator(validate_url)]

class Valves(BaseModel):
    api_url: Url = Field(default="https://api.example.com")
```

## Async Programming

### Always Use Async for I/O Operations

Open WebUI is moving to fully async execution. All I/O operations must be async.

```python
# Good: Async I/O
async def fetch_data(self, url: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

# Avoid: Synchronous I/O (blocks event loop)
def fetch_data(self, url: str) -> dict:
    response = requests.get(url)
    return response.json()
```

### Use Async Libraries

- `aiohttp` instead of `requests`
- `asyncio.sleep()` instead of `time.sleep()`
- `aiofiles` for file I/O
- Native async support for databases

```python
import asyncio
import aiohttp

async def fetch_with_retry(url: str, max_retries: int = 3) -> dict:
    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    response.raise_for_status()
                    return await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
```

### Handle Concurrent Operations

```python
import asyncio

async def process_multiple(urls: list[str]) -> list[dict]:
    """Process multiple URLs concurrently."""
    tasks = [fetch_data(url) for url in urls]
    return await asyncio.gather(*tasks, return_exceptions=True)
```

## Error Handling

### Always Implement Try-Except Blocks

```python
async def pipe(self, body: dict, __event_emitter__=None) -> dict | str:
    try:
        # Operation
        result = await perform_operation()
        
        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {"description": "Success", "done": True}
            })
        
        return result
        
    except ValueError as e:
        # Specific error handling
        error_msg = f"Invalid input: {str(e)}"
        
    except requests.exceptions.Timeout:
        error_msg = "Request timed out. Please try again."
        
    except Exception as e:
        # Catch-all for unexpected errors
        error_msg = f"Unexpected error: {str(e)}"
    
    # Send error notification
    if __event_emitter__:
        await __event_emitter__({
            "type": "notification",
            "data": {"type": "error", "content": error_msg}
        })
    
    return {"content": error_msg}
```

### Provide Meaningful Error Messages

```python
# Good: Actionable error message
"API key is invalid. Please check your Valves configuration and ensure the key starts with 'sk-'."

# Avoid: Vague error message
"Error occurred"
```

### Log Errors for Debugging

```python
import logging

logger = logging.getLogger(__name__)

try:
    result = await operation()
except Exception as e:
    logger.error(f"Operation failed: {e}", exc_info=True)
    raise
```

## Configuration Management

### Use Valves for All Configuration

```python
class Valves(BaseModel):
    # Required settings
    api_key: str = Field(
        default="",
        description="API key for authentication. Required."
    )
    
    # Optional settings with sensible defaults
    api_url: str = Field(
        default="https://api.example.com",
        description="Base URL for API requests"
    )
    
    timeout: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Request timeout in seconds (1-300)"
    )
    
    # Dropdown options using enum
    mode: str = Field(
        default="standard",
        description="Processing mode",
        json_schema_extra={"enum": ["standard", "advanced", "custom"]}
    )
```

### Validate Configuration on Init

```python
def __init__(self):
    self.valves = self.Valves()
    self._validate_configuration()

def _validate_configuration(self):
    """Validate configuration on initialization."""
    if not self.valves.api_key:
        logger.warning("API key not configured. Please set in Valves.")
```

## Security

### Never Hardcode Secrets

```python
# Good: Use Valves
class Valves(BaseModel):
    api_key: str = Field(default="", description="API key")

# Avoid: Hardcoded secrets
API_KEY = "sk-1234567890abcdef"  # NEVER DO THIS
```

### Validate and Sanitize Inputs

```python
import re

def sanitize_input(text: str) -> str:
    """Remove potentially harmful content from input."""
    # Remove script tags
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Remove other potentially harmful patterns
    return text.strip()

async def inlet(self, body: dict) -> dict:
    """Pre-process user input with sanitization."""
    if body.get("messages"):
        last_message = body["messages"][-1]
        if "content" in last_message:
            last_message["content"] = sanitize_input(last_message["content"])
    return body
```

### Implement Rate Limiting

```python
import time
from collections import deque

class RateLimiter:
    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self.calls = deque()
    
    async def acquire(self):
        """Wait if rate limit is exceeded."""
        now = time.time()
        
        # Remove old calls outside the period
        while self.calls and self.calls[0] < now - self.period:
            self.calls.popleft()
        
        # Wait if limit reached
        if len(self.calls) >= self.max_calls:
            sleep_time = self.period - (now - self.calls[0])
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        
        self.calls.append(time.time())
```

### Secure External API Calls

```python
import ssl
import certifi

# Use verified SSL connections
ssl_context = ssl.create_default_context(cafile=certifi.where())

async with aiohttp.ClientSession() as session:
    async with session.get(
        url,
        ssl=ssl_context,
        headers={"Authorization": f"Bearer {self.valves.api_key}"}
    ) as response:
        return await response.json()
```

## Performance

### Implement Caching

```python
from functools import lru_cache
import time

class SmartCache:
    def __init__(self, ttl: int = 3600):
        self._cache = {}
        self._timestamps = {}
        self.ttl = ttl
    
    def get(self, key: str) -> Any | None:
        if key in self._cache:
            if time.time() - self._timestamps[key] < self.ttl:
                return self._cache[key]
            else:
                del self._cache[key]
                del self._timestamps[key]
        return None
    
    def set(self, key: str, value: Any):
        self._cache[key] = value
        self._timestamps[key] = time.time()
```

### Use Connection Pooling

```python
import aiohttp

class Pipe:
    def __init__(self):
        self.valves = self.Valves()
        self._session = None
    
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create persistent session with connection pooling."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=30,
                ttl_dns_cache=300
            )
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session
```

### Implement Timeouts

```python
import asyncio

# Set timeout for operations
try:
    result = await asyncio.wait_for(
        slow_operation(),
        timeout=self.valves.timeout
    )
except asyncio.TimeoutError:
    return {"content": "Operation timed out"}
```

## User Experience

### Provide Status Updates

```python
async def pipe(self, body: dict, __event_emitter__=None):
    if __event_emitter__:
        # Starting
        await __event_emitter__({
            "type": "status",
            "data": {"description": "Starting process...", "done": False}
        })
        
        # Progress update
        await __event_emitter__({
            "type": "status",
            "data": {"description": "Processing data...", "done": False}
        })
        
        # Completion
        await __event_emitter__({
            "type": "status",
            "data": {"description": "Complete", "done": True}
        })
```

### Request Confirmation for Destructive Actions

```python
async def action(self, body: dict, __event_call__=None):
    if __event_call__:
        response = await __event_call__({
            "type": "confirmation",
            "data": {
                "title": "Confirm Deletion",
                "message": "This will permanently delete the data. Continue?"
            }
        })
        
        if not response:
            return {"content": "Action cancelled"}
```

### Use Appropriate Notification Types

```python
# Info notification
await __event_emitter__({
    "type": "notification",
    "data": {"type": "info", "content": "Processing started"}
})

# Success notification
await __event_emitter__({
    "type": "notification",
    "data": {"type": "success", "content": "Operation completed successfully"}
})

# Warning notification
await __event_emitter__({
    "type": "notification",
    "data": {"type": "warning", "content": "API rate limit approaching"}
})

# Error notification
await __event_emitter__({
    "type": "notification",
    "data": {"type": "error", "content": "Operation failed"}
})
```

## Documentation

### Complete Metadata in Docstring

```python
"""
title: Advanced Data Processor
author: Your Name
author_url: https://github.com/username
funding_url: https://github.com/open-webui
version: 1.2.0
required_open_webui_version: 0.4.0
requirements: aiohttp, pydantic, tiktoken
license: MIT
description: Advanced data processing with caching, retry logic, and rate limiting. Supports multiple output formats and streaming responses.
"""
```

### Document Valves Configuration

```python
class Valves(BaseModel):
    api_key: str = Field(
        default="",
        description="Your API key from https://platform.example.com/api-keys"
    )
    
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Number of retry attempts for failed requests (0-10)"
    )
```

### Add Inline Comments for Complex Logic

```python
# Extract model ID from the full model name
# Format: "provider.model_id" -> "model_id"
model_id = body["model"].split(".", 1)[1] if "." in body["model"] else body["model"]

# Prepare payload with extracted model ID
payload = {**body, "model": model_id}
```

### Create README Files

Each function should have a README.md with:

- Overview and purpose
- Installation requirements
- Configuration instructions
- Usage examples
- Troubleshooting tips
- Known limitations

## Testing

### Test Coverage Checklist

- [ ] Function loads without errors
- [ ] Valid inputs produce expected outputs
- [ ] Invalid inputs show helpful error messages
- [ ] Edge cases are handled (empty strings, null values, etc.)
- [ ] Async operations complete correctly
- [ ] Event emitters send proper notifications
- [ ] Streaming responses work
- [ ] Configuration validation works
- [ ] Error recovery functions properly
- [ ] Performance is acceptable under load

### Manual Testing Scenarios

1. **Happy path**: Valid configuration, normal inputs
2. **Missing configuration**: Empty API keys, missing URLs
3. **Invalid inputs**: Malformed data, unexpected types
4. **Network errors**: Timeouts, connection failures
5. **API errors**: Rate limits, authentication failures
6. **Edge cases**: Very long inputs, special characters
7. **Concurrent requests**: Multiple simultaneous operations

### Example Test Cases

```python
# Test 1: Valid operation
body = {
    "messages": [{"role": "user", "content": "test"}],
    "model": "test-model"
}
result = await pipe.pipe(body)
assert result is not None

# Test 2: Missing API key
pipe.valves.api_key = ""
result = await pipe.pipe(body)
assert "error" in str(result).lower()

# Test 3: Timeout handling
pipe.valves.timeout = 0.001  # Very short timeout
result = await pipe.pipe(body)
# Should handle timeout gracefully
```

---

## Quick Reference

### Function Template

```python
"""
title: Function Name
author: Author Name
version: 1.0.0
required_open_webui_version: 0.4.0
requirements: aiohttp, pydantic
license: MIT
"""

from pydantic import BaseModel, Field
from typing import Any, Callable
import asyncio

class Pipe:  # or Filter, Action, Tools
    class Valves(BaseModel):
        api_key: str = Field(default="", description="API key")
        timeout: int = Field(default=30, ge=1, description="Timeout in seconds")
    
    def __init__(self):
        self.valves = self.Valves()
    
    async def pipe(
        self,
        body: dict[str, Any],
        __user__: dict[str, Any] | None = None,
        __event_emitter__: Callable[[dict], Any] | None = None,
    ) -> dict[str, Any] | str:
        try:
            if __event_emitter__:
                await __event_emitter__({
                    "type": "status",
                    "data": {"description": "Processing...", "done": False}
                })
            
            # Your logic here
            result = await self.process(body)
            
            if __event_emitter__:
                await __event_emitter__({
                    "type": "status",
                    "data": {"description": "Complete", "done": True}
                })
            
            return result
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            
            if __event_emitter__:
                await __event_emitter__({
                    "type": "notification",
                    "data": {"type": "error", "content": error_msg}
                })
            
            return {"content": error_msg}
    
    async def process(self, body: dict) -> dict:
        """Process the request."""
        # Implementation
        pass
```

---

## Additional Resources

- [Open WebUI Documentation](https://docs.openwebui.com/)
- [Python Typing Best Practices](https://typing.python.org/en/latest/reference/best_practices.html)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [FastAPI Best Practices](https://github.com/zhanymkanov/fastapi-best-practices)
- [Async Python Guide](https://docs.python.org/3/library/asyncio.html)
