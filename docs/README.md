# Open WebUI Extension Development Documentation

Comprehensive guides for developing high-quality Open WebUI extensions (Pipes, Filters, Actions, and Tools).

## Quick Start

1. Read the [Best Practices](best-practices.md) guide
2. Choose your function type and read the specific guide:
   - [Pipes Guide](pipes-guide.md) - Custom models and integrations
   - [Filters Guide](filters-guide.md) - Input/output modification
   - [Actions Guide](actions-guide.md) - Interactive message buttons
   - [Tools Guide](tools-guide.md) - Function calling capabilities
3. Review [Python Standards](python-standards.md) for coding conventions
4. Follow the [Testing Guide](testing-guide.md) to validate your work

## Documentation Overview

### Core Guides

**[Best Practices](best-practices.md)**
Essential patterns and practices for all Open WebUI extensions:
- Code quality and modern Python syntax
- Type safety with comprehensive type hints
- Async programming patterns
- Error handling strategies
- Configuration management with Valves
- Security best practices
- Performance optimization
- User experience guidelines
- Documentation standards
- Testing approaches

**[Python Standards](python-standards.md)**
Python coding conventions specific to Open WebUI development:
- Modern type hints (Python 3.10+)
- Pydantic 2 usage patterns
- Async/await best practices
- Code formatting and style
- Import organization
- Naming conventions

**[Testing Guide](testing-guide.md)**
Comprehensive testing strategies for extensions:
- Manual testing procedures
- Unit testing examples
- Integration testing approaches
- Performance testing
- Security testing
- Edge case coverage

### Function-Specific Guides

**[Pipes Guide](pipes-guide.md)**
Build custom models and integrations:
- When to use Pipes
- Basic structure and patterns
- Creating multiple models (manifold pattern)
- Handling streaming responses
- Model ID extraction
- OpenAI/Anthropic/Google proxy examples
- Using internal Open WebUI functions
- Error handling and retry logic
- Performance optimization
- Complete working examples

**[Filters Guide](filters-guide.md)**
Modify inputs, outputs, and streaming responses:
- When to use Filters
- Always-on vs toggleable filters
- inlet() - Pre-process user inputs
- stream() - Modify streaming responses
- outlet() - Post-process model outputs
- Filter priority and execution order
- Global vs model-specific configuration
- Content moderation examples
- Context injection patterns
- Translation and logging examples

**[Actions Guide](actions-guide.md)**
Create interactive message toolbar buttons:
- When to use Actions
- Basic structure and patterns
- Event system integration
- User confirmations and input dialogs
- Single vs multi-action functions
- Working with uploaded files
- User permission checks
- Background task execution
- Complete working examples (summarizer, code formatter)

**[Tools Guide](tools-guide.md)**
Enable model function calling:
- When to use Tools
- Critical requirements (type hints, docstrings)
- Structured return types with TypedDict
- Multiple tools in one class
- Complex parameter types
- Error handling patterns
- Caching and rate limiting
- Complete web search tool example

## Function Type Decision Guide

### Choose a Pipe when:
- Creating a proxy to an external AI service (OpenAI, Anthropic, Google)
- Building a custom agent with specific behavior
- Combining multiple models or services
- Creating non-AI integrations (search, home automation, APIs)
- You want it to appear as a selectable "model"

### Choose a Filter when:
- Modifying user inputs before sending to model (add context, sanitize)
- Processing streaming responses in real-time
- Cleaning up or formatting model outputs
- Implementing content moderation or PII scrubbing
- Adding automatic instructions or context
- Logging conversations

### Choose an Action when:
- Adding interactive buttons to the message toolbar
- Creating optional user-triggered functionality
- Requiring user confirmation before operations
- Generating visualizations or downloads from messages
- Processing or transforming existing message content
- Providing quick access to common operations

### Choose a Tool when:
- Enabling model function calling capabilities
- Creating utility functions the model can invoke automatically
- Building integrations the model uses based on conversation
- Providing structured data retrieval on demand
- Performing calculations or data processing when needed

## Quick Reference Templates

### Pipe Template
```python
"""
title: My Pipe
author: Your Name
version: 1.0.0
required_open_webui_version: 0.4.0
requirements: aiohttp
"""

from pydantic import BaseModel, Field
from typing import Any, Callable

class Pipe:
    class Valves(BaseModel):
        API_KEY: str = Field(default="")
    
    def __init__(self):
        self.valves = self.Valves()
    
    async def pipe(
        self,
        body: dict[str, Any],
        __user__: dict | None = None,
        __event_emitter__: Callable | None = None,
    ) -> dict | str:
        # Implementation
        pass
```

### Filter Template
```python
"""
title: My Filter
author: Your Name
version: 1.0.0
required_open_webui_version: 0.4.0
"""

from pydantic import BaseModel, Field

class Filter:
    class Valves(BaseModel):
        priority: int = Field(default=0)
    
    def __init__(self):
        self.valves = self.Valves()
        self.toggle = True  # Optional: make toggleable
    
    async def inlet(self, body: dict) -> dict:
        return body
    
    def stream(self, event: dict) -> dict:
        return event
    
    async def outlet(self, body: dict) -> dict:
        return body
```

### Action Template
```python
"""
title: My Action
author: Your Name
version: 1.0.0
required_open_webui_version: 0.4.0
icon_url: data:image/svg+xml;base64,...
"""

from pydantic import BaseModel
from typing import Any, Callable

class Action:
    class Valves(BaseModel):
        pass
    
    def __init__(self):
        self.valves = self.Valves()
    
    async def action(
        self,
        body: dict[str, Any],
        __event_emitter__: Callable | None = None,
        __event_call__: Callable | None = None,
    ) -> dict[str, Any]:
        return {"content": "Action result"}
```

### Tool Template
```python
"""
title: My Tool
author: Your Name
version: 1.0.0
required_open_webui_version: 0.4.0
"""

from pydantic import BaseModel
from typing import Any, Callable

class Tools:
    class Valves(BaseModel):
        pass
    
    def __init__(self):
        self.valves = self.Valves()
    
    async def my_function(
        self,
        parameter: str,
        __event_emitter__: Callable | None = None,
    ) -> str:
        """
        Function description for the model.
        
        :param parameter: Parameter description
        :return: Return value description
        """
        return f"Result: {parameter}"
```

## Development Workflow

1. **Plan**: Determine which function type fits your use case
2. **Research**: Review similar existing functions in the repository
3. **Design**: Plan Valves configuration, event flow, error handling
4. **Implement**: Write clean, typed, async code following standards
5. **Document**: Add comprehensive docstrings and metadata
6. **Test**: Validate with various inputs and edge cases
7. **Security Review**: Check for vulnerabilities, secrets exposure
8. **Optimize**: Review for performance, caching opportunities
9. **Polish**: Clean up code, add helpful comments
10. **Submit**: Create PR with clear description and examples

## Key Principles

### 1. Always Use Async
Open WebUI is moving to fully async execution. All I/O operations must be async.

### 2. Complete Type Hints
Every parameter and return value needs type hints. They generate the JSON schema.

### 3. Comprehensive Error Handling
Always use try-except blocks with meaningful error messages and notifications.

### 4. Event-Driven Feedback
Use `__event_emitter__` for status updates and notifications on long operations.

### 5. Security First
Never hardcode secrets, validate all inputs, sanitize outputs.

### 6. Test Thoroughly
Validate with different inputs, edge cases, errors, and concurrent requests.

### 7. Document Everything
Clear docstrings, metadata, README files, and inline comments.

## Common Patterns

### Status Updates
```python
if __event_emitter__:
    await __event_emitter__({
        "type": "status",
        "data": {"description": "Processing...", "done": False}
    })
```

### User Confirmation
```python
if __event_call__:
    confirmed = await __event_call__({
        "type": "confirmation",
        "data": {"title": "Confirm", "message": "Proceed?"}
    })
```

### Error Notification
```python
if __event_emitter__:
    await __event_emitter__({
        "type": "notification",
        "data": {"type": "error", "content": "Operation failed"}
    })
```

## External Resources

### Official Documentation
- [Open WebUI Docs](https://docs.openwebui.com/)
- [Functions Overview](https://docs.openwebui.com/features/plugin/functions/)
- [Event System](https://docs.openwebui.com/features/plugin/events/)

### Community
- [Open WebUI GitHub](https://github.com/open-webui/open-webui)
- [Functions Repository](https://github.com/open-webui/functions)
- [Community Functions](https://openwebui.com/)

### Python Resources
- [Type Hints Best Practices](https://typing.python.org/en/latest/reference/best_practices.html)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Async Python Guide](https://docs.python.org/3/library/asyncio.html)
- [FastAPI Best Practices](https://github.com/zhanymkanov/fastapi-best-practices)

## Getting Help

1. Check this documentation first
2. Review similar functions in the repository
3. Search existing GitHub issues
4. Ask in Open WebUI Discord/community
5. Create a GitHub issue with:
   - Clear description of problem
   - Code example (minimal reproducible example)
   - Expected vs actual behavior
   - Environment details (Open WebUI version, Python version)

## Contributing

When contributing to the Open WebUI functions repository:

1. Follow all guidelines in this documentation
2. Ensure your code passes all tests
3. Include comprehensive documentation
4. Add usage examples
5. Update README if adding new patterns
6. Follow existing code conventions
7. Make atomic, focused commits
8. Write clear PR descriptions

---

For the most up-to-date information, always refer to the [official Open WebUI documentation](https://docs.openwebui.com/).

Happy coding! 🚀
