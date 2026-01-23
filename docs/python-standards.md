# Python Coding Standards for Open WebUI Extensions

Python coding conventions and standards specific to Open WebUI extension development.

## Table of Contents

- [Modern Python Syntax](#modern-python-syntax)
- [Type Hints](#type-hints)
- [Pydantic 2 Patterns](#pydantic-2-patterns)
- [Async/Await](#asyncawait)
- [Code Formatting](#code-formatting)
- [Import Organization](#import-organization)
- [Naming Conventions](#naming-conventions)
- [Documentation](#documentation)
- [Error Handling](#error-handling)

## Modern Python Syntax

### Use Python 3.10+ Features

Open WebUI extensions should use modern Python 3.10+ syntax:

```python
# Good: Modern union syntax (PEP 604)
def process(value: str | None) -> list[dict[str, str]]:
    pass

# Avoid: Old-style typing (deprecated)
from typing import Optional, List, Dict
def process(value: Optional[str]) -> List[Dict[str, str]]:
    pass
```

### Prefer Built-in Generic Types

```python
# Good: Built-in generics (Python 3.9+)
def get_items() -> list[str]:
    return ["item1", "item2"]

def get_mapping() -> dict[str, int]:
    return {"count": 42}

# Avoid: typing module imports for basic types
from typing import List, Dict
def get_items() -> List[str]:
    return ["item1", "item2"]
```

### Pattern Matching

Use pattern matching for complex conditionals (Python 3.10+):

```python
def process_event(event: dict) -> str:
    match event:
        case {"type": "status", "data": data}:
            return f"Status: {data}"
        case {"type": "error", "message": msg}:
            return f"Error: {msg}"
        case _:
            return "Unknown event"
```

## Type Hints

### Complete Type Annotations

**All functions must have complete type hints:**

```python
# Good: Complete type hints
async def fetch_data(
    url: str,
    timeout: int = 30,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    pass

# Bad: Missing or incomplete type hints
async def fetch_data(url, timeout=30, headers=None):
    pass
```

### Use Type Aliases for Clarity

```python
from typing import TypeAlias

# Define reusable type aliases
UserId: TypeAlias = str
Timestamp: TypeAlias = int
UserData: TypeAlias = dict[str, Any]

def get_user(user_id: UserId) -> UserData:
    pass
```

### Annotated Types for Constraints

Use `Annotated` for validation constraints:

```python
from typing import Annotated
from pydantic import Field, AfterValidator

def validate_positive(v: int) -> int:
    if v <= 0:
        raise ValueError("Must be positive")
    return v

PositiveInt = Annotated[int, AfterValidator(validate_positive)]

class Valves(BaseModel):
    count: PositiveInt = Field(default=1)
```

### TypedDict for Structured Dicts

Use `TypedDict` for dictionaries with known structure:

```python
from typing import TypedDict

class UserInfo(TypedDict):
    id: str
    name: str
    email: str
    role: str

class MessageData(TypedDict, total=False):  # total=False makes all fields optional
    content: str
    role: str
    files: list[dict[str, str]]

def process_user(user: UserInfo) -> None:
    # Type checker knows the structure
    print(user["name"])
```

### Literal Types for Constants

```python
from typing import Literal

Role = Literal["user", "admin", "moderator"]

def check_permission(role: Role) -> bool:
    return role in ("admin", "moderator")

# Type checker ensures only valid values
check_permission("user")  # ✓ OK
check_permission("guest")  # ✗ Type error
```

### Generic Types

```python
from typing import TypeVar, Generic

T = TypeVar("T")

class Cache(Generic[T]):
    def __init__(self):
        self._data: dict[str, T] = {}
    
    def get(self, key: str) -> T | None:
        return self._data.get(key)
    
    def set(self, key: str, value: T) -> None:
        self._data[key] = value

# Usage
cache: Cache[str] = Cache()
cache.set("key", "value")
```

## Pydantic 2 Patterns

### Model Configuration

```python
from pydantic import BaseModel, Field, ConfigDict

class Valves(BaseModel):
    # Pydantic 2 configuration
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=True,
    )
    
    api_key: str = Field(
        default="",
        min_length=1,
        description="API key for authentication"
    )
```

### Field Validation

```python
from pydantic import BaseModel, Field, field_validator

class Valves(BaseModel):
    api_key: str = Field(default="")
    timeout: int = Field(default=30, ge=1, le=300)
    
    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if v and not v.startswith("sk-"):
            raise ValueError("API key must start with 'sk-'")
        return v
    
    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        if v < 1 or v > 300:
            raise ValueError("Timeout must be between 1 and 300")
        return v
```

### Computed Fields

```python
from pydantic import BaseModel, computed_field

class Config(BaseModel):
    api_url: str
    api_path: str
    
    @computed_field
    @property
    def full_url(self) -> str:
        return f"{self.api_url.rstrip('/')}/{self.api_path.lstrip('/')}"
```

### Model Serialization

```python
class UserData(BaseModel):
    name: str
    email: str
    password: str = Field(exclude=True)  # Never serialize
    
    def model_dump_safe(self) -> dict[str, Any]:
        """Return safe serialization without sensitive fields."""
        return self.model_dump(exclude={"password"})
```

## Async/Await

### Always Use Async for I/O

```python
# Good: Async I/O operations
async def fetch_data(url: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

# Bad: Blocking I/O (blocks event loop)
def fetch_data(url: str) -> dict:
    response = requests.get(url)
    return response.json()
```

### Async Context Managers

```python
import asyncio
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_session():
    """Async context manager for HTTP session."""
    session = aiohttp.ClientSession()
    try:
        yield session
    finally:
        await session.close()

# Usage
async with get_session() as session:
    async with session.get(url) as response:
        data = await response.json()
```

### Concurrent Operations

```python
import asyncio

async def process_multiple(items: list[str]) -> list[dict]:
    """Process multiple items concurrently."""
    # Run all tasks concurrently
    tasks = [process_item(item) for item in items]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Filter out exceptions
    return [r for r in results if not isinstance(r, Exception)]
```

### Async Generators

```python
from typing import AsyncGenerator

async def stream_data(url: str) -> AsyncGenerator[bytes, None]:
    """Stream data from URL."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            async for chunk in response.content.iter_chunked(1024):
                yield chunk

# Usage
async for chunk in stream_data(url):
    process(chunk)
```

## Code Formatting

### Line Length

Maximum line length: **100 characters**

```python
# Good: Within line length
async def process_data(
    input_data: dict[str, Any],
    options: ProcessOptions | None = None,
) -> ProcessResult:
    pass

# Avoid: Too long
async def process_data(input_data: dict[str, Any], options: ProcessOptions | None = None) -> ProcessResult:
    pass
```

### String Formatting

Prefer f-strings:

```python
# Good: F-strings (Python 3.6+)
name = "Alice"
age = 30
message = f"Hello {name}, you are {age} years old"

# Avoid: Old-style formatting
message = "Hello %s, you are %d years old" % (name, age)
message = "Hello {}, you are {} years old".format(name, age)
```

### Multi-line Collections

Use trailing commas for multi-line collections:

```python
# Good: Trailing comma
users = [
    "alice",
    "bob",
    "charlie",  # ← trailing comma
]

config = {
    "api_key": "...",
    "timeout": 30,
    "retries": 3,  # ← trailing comma
}

# Makes adding/removing items easier and cleaner diffs
```

### Line Breaks

```python
# Good: Break before binary operators
total = (
    first_value
    + second_value
    + third_value
    - deduction
)

# Good: Align continuation lines
result = some_function(
    first_argument="value1",
    second_argument="value2",
    third_argument="value3",
)
```

## Import Organization

### Import Grouping

Group imports in this order:

1. Standard library imports
2. Related third-party imports
3. Local application/library imports

```python
# Standard library
import asyncio
import logging
from typing import Any, Callable

# Third-party
import aiohttp
from pydantic import BaseModel, Field

# Local/Open WebUI
from open_webui.models.users import Users
from open_webui.utils.chat import generate_chat_completion
```

### Import Style

```python
# Good: Explicit imports
from typing import Any, Callable, TypedDict
from pydantic import BaseModel, Field

# Avoid: Wildcard imports
from typing import *
from pydantic import *

# Avoid: Unused imports (use tools to detect)
from typing import Any, Callable, List  # List is unused
```

### Relative vs Absolute Imports

```python
# Good: Absolute imports (preferred in Open WebUI)
from open_webui.utils.chat import generate_chat_completion

# Acceptable: Relative imports within same package
from .utils import helper_function
```

## Naming Conventions

### Variables and Functions

```python
# Variables and functions: snake_case
user_count = 10
api_key = "..."

def calculate_total(items: list[int]) -> int:
    pass

async def fetch_user_data(user_id: str) -> dict:
    pass
```

### Classes

```python
# Classes: PascalCase
class UserManager:
    pass

class DataProcessor:
    pass

class APIClient:
    pass
```

### Constants

```python
# Constants: UPPER_SNAKE_CASE
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30
API_BASE_URL = "https://api.example.com"
```

### Type Aliases

```python
# Type aliases: PascalCase
UserId = str
UserData = dict[str, Any]
ProcessResult = tuple[bool, str]
```

### Private Members

```python
class MyClass:
    def __init__(self):
        self._private = "internal use"  # Single underscore
        self.__really_private = "name mangled"  # Double underscore
    
    def _internal_method(self):
        """Internal helper method."""
        pass
    
    def public_method(self):
        """Public API method."""
        pass
```

### Special Names

```python
# Avoid name conflicts with builtins
list_ = []  # Append underscore
dict_ = {}
type_ = "example"

# Better: Use more descriptive names
items = []
mapping = {}
data_type = "example"
```

## Documentation

### Module Docstrings

```python
"""
title: Web Search Tool
author: Open WebUI Team
author_url: https://github.com/open-webui
version: 1.0.0
required_open_webui_version: 0.4.0
requirements: aiohttp, beautifulsoup4
license: MIT
description: Search the web and retrieve relevant information with caching and rate limiting
"""
```

### Function Docstrings

```python
async def search_web(
    query: str,
    num_results: int = 10,
    language: str = "en",
) -> list[dict[str, str]]:
    """
    Search the web for information.
    
    Performs a web search using the configured search API and returns
    formatted results. Includes automatic rate limiting and caching.
    
    Args:
        query: Search query string
        num_results: Maximum number of results to return (1-50)
        language: Language code for results (default: "en")
    
    Returns:
        List of search results, each containing:
        - title: Result title
        - url: Result URL
        - snippet: Result description/snippet
    
    Raises:
        ValueError: If query is empty or num_results is out of range
        APIError: If the search API returns an error
    
    Example:
        >>> results = await search_web("Python programming", num_results=5)
        >>> print(results[0]["title"])
        "Python Tutorial"
    """
    pass
```

### Inline Comments

```python
# Good: Explain WHY, not WHAT
# Extract model ID from full name format: "provider.model_id"
model_id = body["model"].split(".", 1)[1]

# Bad: Redundant comment
# Split the model name
model_id = body["model"].split(".", 1)[1]
```

## Error Handling

### Specific Exception Types

```python
# Good: Catch specific exceptions
try:
    result = await fetch_data(url)
except aiohttp.ClientResponseError as e:
    logger.error(f"HTTP error {e.status}: {e.message}")
except aiohttp.ClientError as e:
    logger.error(f"Network error: {str(e)}")
except ValueError as e:
    logger.error(f"Invalid data: {str(e)}")

# Avoid: Bare except
try:
    result = await fetch_data(url)
except:  # Don't do this!
    pass
```

### Exception Context

```python
# Good: Preserve exception context
try:
    data = parse_json(text)
except json.JSONDecodeError as e:
    raise ValueError(f"Invalid JSON data: {text[:100]}...") from e

# Avoid: Losing context
try:
    data = parse_json(text)
except json.JSONDecodeError:
    raise ValueError("Invalid JSON")
```

### Custom Exceptions

```python
class OpenWebUIError(Exception):
    """Base exception for Open WebUI extensions."""
    pass

class APIError(OpenWebUIError):
    """API request failed."""
    def __init__(self, status: int, message: str):
        self.status = status
        super().__init__(f"API error {status}: {message}")

class ValidationError(OpenWebUIError):
    """Input validation failed."""
    pass
```

## Code Quality Tools

### Recommended Tools

- **ruff**: Fast linter and formatter
- **mypy**: Static type checker
- **pytest**: Testing framework
- **black**: Code formatter (if not using ruff)

### Configuration Example

```toml
# pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py310"

[tool.mypy]
python_version = "3.10"
strict = true
warn_return_any = true
warn_unused_configs = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

## Additional Resources

- [PEP 8 – Style Guide for Python Code](https://peps.python.org/pep-0008/)
- [PEP 484 – Type Hints](https://peps.python.org/pep-0484/)
- [PEP 604 – Union Type Operator](https://peps.python.org/pep-0604/)
- [Pydantic V2 Documentation](https://docs.pydantic.dev/)
- [Python Type Hints](https://typing.python.org/en/latest/)
- [FastAPI Best Practices](https://github.com/zhanymkanov/fastapi-best-practices)
