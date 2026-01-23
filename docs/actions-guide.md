# Actions Development Guide

Actions are custom buttons that appear in the message toolbar, allowing users to interact with messages through clickable interfaces. Use Actions for optional, user-triggered functionality.

## When to Use Actions

Use an Action when you want to:

- Add interactive buttons to messages
- Create optional user-triggered functionality
- Require user confirmation before operations
- Generate visualizations or downloads from message content
- Process or transform existing messages
- Provide quick access to common operations

## Basic Structure

```python
"""
title: My Custom Action
author: Your Name
version: 1.0.0
required_open_webui_version: 0.4.0
requirements: requests
icon_url: data:image/svg+xml;base64,...
"""

from pydantic import BaseModel, Field
from typing import Any, Callable

class Action:
    class Valves(BaseModel):
        API_KEY: str = Field(
            default="",
            description="API key for service"
        )
    
    def __init__(self):
        self.valves = self.Valves()
    
    async def action(
        self,
        body: dict[str, Any],
        __user__: dict[str, Any] | None = None,
        __event_emitter__: Callable[[dict], Any] | None = None,
        __event_call__: Callable[[dict], Any] | None = None,
    ) -> dict[str, Any]:
        """
        Process action request.
        
        Args:
            body: Message data and context
            __user__: User information
            __event_emitter__: Send status updates/notifications
            __event_call__: Request user input/confirmation
        
        Returns:
            Modified message content
        """
        # Your implementation
        return {"content": "Action completed"}
```

## Action Method Parameters

### body: dict

Contains message data and context:

```python
{
    "messages": [
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."}
    ],
    "content": "Current message content",
    "files": [
        {"type": "image", "url": "...", "name": "..."}
    ]
}
```

### __user__: dict

User information:

```python
{
    "id": "user-123",
    "name": "John Doe",
    "email": "john@example.com",
    "role": "user"  # or "admin"
}
```

### __event_emitter__: Callable

Send real-time updates:

```python
# Status update
await __event_emitter__({
    "type": "status",
    "data": {
        "description": "Processing...",
        "done": False
    }
})

# Notification
await __event_emitter__({
    "type": "notification",
    "data": {
        "type": "info",  # or "success", "warning", "error"
        "content": "Operation completed"
    }
})
```

### __event_call__: Callable

Request user input:

```python
# Confirmation dialog
response = await __event_call__({
    "type": "confirmation",
    "data": {
        "title": "Confirm Action",
        "message": "Are you sure you want to proceed?"
    }
})
# Returns: True or False

# Input dialog
user_input = await __event_call__({
    "type": "input",
    "data": {
        "title": "Enter Value",
        "message": "Please provide details:",
        "placeholder": "Type here..."
    }
})
# Returns: str (user input)
```

### __model__: dict (optional)

Model information:

```python
{
    "id": "gpt-4",
    "name": "GPT-4"
}
```

### __request__: Request (optional)

FastAPI request object for accessing headers, etc.

## Single Action Example

```python
"""
title: Message Summarizer
author: Open WebUI Team
version: 1.0.0
required_open_webui_version: 0.4.0
description: Summarize message content with configurable length
icon_url: data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIGZpbGw9Im5vbmUiIHZpZXdCb3g9IjAgMCAyNCAyNCIgc3Ryb2tlPSJjdXJyZW50Q29sb3IiPjxwYXRoIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgc3Ryb2tlLXdpZHRoPSIyIiBkPSJNNCA2aDE2TTQgMTJoMTZNNCAxOGg3Ii8+PC9zdmc+
"""

from pydantic import BaseModel, Field
from typing import Any, Callable
import aiohttp

class Action:
    class Valves(BaseModel):
        API_KEY: str = Field(
            default="",
            description="OpenAI API key"
        )
        MAX_LENGTH: int = Field(
            default=100,
            ge=50,
            le=500,
            description="Maximum summary length in words"
        )
    
    def __init__(self):
        self.valves = self.Valves()
    
    async def action(
        self,
        body: dict[str, Any],
        __user__: dict[str, Any] | None = None,
        __event_emitter__: Callable[[dict], Any] | None = None,
        __event_call__: Callable[[dict], Any] | None = None,
    ) -> dict[str, Any]:
        """Summarize the message content."""
        
        # Check API key
        if not self.valves.API_KEY:
            if __event_emitter__:
                await __event_emitter__({
                    "type": "notification",
                    "data": {
                        "type": "error",
                        "content": "API key not configured"
                    }
                })
            return {"content": "Error: API key required"}
        
        # Get message content
        content = body.get("content", "")
        
        if not content:
            return {"content": "Error: No content to summarize"}
        
        # Request confirmation
        if __event_call__:
            confirmed = await __event_call__({
                "type": "confirmation",
                "data": {
                    "title": "Summarize Message",
                    "message": f"Summarize this message ({len(content)} chars)?"
                }
            })
            
            if not confirmed:
                return {"content": "Summarization cancelled"}
        
        # Show progress
        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {
                    "description": "Generating summary...",
                    "done": False
                }
            })
        
        try:
            # Call summarization API
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    json={
                        "model": "gpt-4",
                        "messages": [
                            {
                                "role": "system",
                                "content": f"Summarize the following text in {self.valves.MAX_LENGTH} words or less."
                            },
                            {
                                "role": "user",
                                "content": content
                            }
                        ]
                    },
                    headers={
                        "Authorization": f"Bearer {self.valves.API_KEY}",
                        "Content-Type": "application/json"
                    },
                    timeout=30
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
                    
                    summary = result["choices"][0]["message"]["content"]
                    
                    # Success notification
                    if __event_emitter__:
                        await __event_emitter__({
                            "type": "status",
                            "data": {
                                "description": "Summary generated",
                                "done": True
                            }
                        })
                        
                        await __event_emitter__({
                            "type": "notification",
                            "data": {
                                "type": "success",
                                "content": "Message summarized successfully"
                            }
                        })
                    
                    # Return modified content
                    return {
                        "content": f"**Summary:**\n\n{summary}\n\n---\n\n**Original:**\n\n{content}"
                    }
        
        except Exception as e:
            if __event_emitter__:
                await __event_emitter__({
                    "type": "notification",
                    "data": {
                        "type": "error",
                        "content": f"Summarization failed: {str(e)}"
                    }
                })
            
            return {"content": f"Error: {str(e)}"}
```

## Multi-Action Example

Define multiple actions with an `actions` array:

```python
"""
title: Text Utilities
author: Open WebUI Team
version: 1.0.0
required_open_webui_version: 0.4.0
description: Multiple text processing actions
"""

from pydantic import BaseModel
from typing import Any, Callable

class Action:
    class Valves(BaseModel):
        pass
    
    def __init__(self):
        self.valves = self.Valves()
    
    # Define available actions
    actions = [
        {
            "id": "uppercase",
            "name": "Convert to Uppercase",
            "icon_url": "data:image/svg+xml;base64,..."
        },
        {
            "id": "lowercase",
            "name": "Convert to Lowercase",
            "icon_url": "data:image/svg+xml;base64,..."
        },
        {
            "id": "word_count",
            "name": "Count Words",
            "icon_url": "data:image/svg+xml;base64,..."
        }
    ]
    
    async def action(
        self,
        body: dict[str, Any],
        __id__: str | None = None,
        __event_emitter__: Callable | None = None,
    ) -> dict[str, Any]:
        """Process action based on __id__."""
        
        content = body.get("content", "")
        
        if __id__ == "uppercase":
            return {"content": content.upper()}
        
        elif __id__ == "lowercase":
            return {"content": content.lower()}
        
        elif __id__ == "word_count":
            word_count = len(content.split())
            
            if __event_emitter__:
                await __event_emitter__({
                    "type": "notification",
                    "data": {
                        "type": "info",
                        "content": f"Word count: {word_count}"
                    }
                })
            
            return {
                "content": f"{content}\n\n---\n**Word count:** {word_count}"
            }
        
        return {"content": "Unknown action"}
```

## Working with Files

Actions can process uploaded files:

```python
async def action(self, body: dict, __event_emitter__=None) -> dict:
    """Process uploaded images."""
    
    files = body.get("files", [])
    
    if not files:
        return {"content": "No files to process"}
    
    processed_files = []
    
    for file in files:
        if file.get("type") == "image":
            # Process image
            processed = await self.process_image(file["url"])
            
            processed_files.append({
                "type": "image",
                "url": processed["url"],
                "name": f"processed_{file['name']}"
            })
    
    return {
        "content": "Images processed successfully",
        "files": processed_files
    }
```

## User Permission Checks

Restrict actions based on user role:

```python
async def action(self, body: dict, __user__=None, __event_emitter__=None):
    """Admin-only action."""
    
    # Check user role
    if not __user__ or __user__.get("role") != "admin":
        if __event_emitter__:
            await __event_emitter__({
                "type": "notification",
                "data": {
                    "type": "error",
                    "content": "This action requires admin privileges"
                }
            })
        return {"content": "Access denied"}
    
    # Proceed with admin action
    return {"content": "Admin action completed"}
```

## Background Task Example

For long-running operations:

```python
import asyncio

async def action(self, body: dict, __event_emitter__=None):
    """Long-running operation with progress updates."""
    
    steps = ["Initializing", "Processing", "Finalizing"]
    
    for i, step in enumerate(steps):
        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {
                    "description": f"{step}... ({i+1}/{len(steps)})",
                    "done": False
                }
            })
        
        # Simulate work
        await asyncio.sleep(2)
    
    if __event_emitter__:
        await __event_emitter__({
            "type": "status",
            "data": {
                "description": "Complete",
                "done": True
            }
        })
    
    return {"content": "Operation completed successfully"}
```

## Global vs Model-Specific Actions

### Global Actions

Apply to all models:

1. Admin Panel → Functions → Actions
2. Click three-dot menu (⋮)
3. Toggle Globe icon (🌐)
4. Ensure action is Active

### Model-Specific Actions

Apply to specific models:

1. Model Settings → Actions
2. Select actions to enable for this model

## Complete Example: Code Formatter

```python
"""
title: Code Formatter
author: Open WebUI Team
version: 1.0.0
required_open_webui_version: 0.4.0
requirements: black, isort
description: Format Python code in messages
icon_url: data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIGZpbGw9Im5vbmUiIHZpZXdCb3g9IjAgMCAyNCAyNCIgc3Ryb2tlPSJjdXJyZW50Q29sb3IiPjxwYXRoIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgc3Ryb2tlLXdpZHRoPSIyIiBkPSJNNyA4aDEwTTcgMTJoNE0xMCAxNmg3TTYgMjBoMTJhMiAyIDAgMCAwIDItMlY2YTIgMiAwIDAgMC0yLTJINmEyIDIgMCAwIDAtMiAydjEyYTIgMiAwIDAgMCAyIDJ6Ii8+PC9zdmc+
"""

from pydantic import BaseModel, Field
from typing import Any, Callable
import re
import black
import isort

class Action:
    class Valves(BaseModel):
        line_length: int = Field(
            default=88,
            ge=50,
            le=120,
            description="Maximum line length for formatting"
        )
        sort_imports: bool = Field(
            default=True,
            description="Sort imports using isort"
        )
    
    def __init__(self):
        self.valves = self.Valves()
    
    def extract_code_blocks(self, content: str) -> list[tuple[str, str]]:
        """Extract Python code blocks from markdown."""
        pattern = r'```python\n(.*?)\n```'
        matches = re.findall(pattern, content, re.DOTALL)
        return matches
    
    def format_code(self, code: str) -> str:
        """Format Python code using black and isort."""
        try:
            # Sort imports
            if self.valves.sort_imports:
                code = isort.code(code)
            
            # Format with black
            code = black.format_str(
                code,
                mode=black.Mode(line_length=self.valves.line_length)
            )
            
            return code.strip()
        
        except Exception as e:
            raise ValueError(f"Formatting failed: {str(e)}")
    
    async def action(
        self,
        body: dict[str, Any],
        __event_emitter__: Callable | None = None,
        __event_call__: Callable | None = None,
    ) -> dict[str, Any]:
        """Format Python code blocks in the message."""
        
        content = body.get("content", "")
        
        if not content:
            return {"content": "No content to format"}
        
        # Extract code blocks
        code_blocks = self.extract_code_blocks(content)
        
        if not code_blocks:
            if __event_emitter__:
                await __event_emitter__({
                    "type": "notification",
                    "data": {
                        "type": "warning",
                        "content": "No Python code blocks found"
                    }
                })
            return {"content": content}
        
        # Request confirmation
        if __event_call__:
            confirmed = await __event_call__({
                "type": "confirmation",
                "data": {
                    "title": "Format Code",
                    "message": f"Format {len(code_blocks)} Python code block(s)?"
                }
            })
            
            if not confirmed:
                return {"content": content}
        
        # Show progress
        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {
                    "description": "Formatting code...",
                    "done": False
                }
            })
        
        try:
            # Format each code block
            formatted_content = content
            
            for i, code_block in enumerate(code_blocks):
                formatted_code = self.format_code(code_block)
                
                # Replace in content
                original_block = f"```python\n{code_block}\n```"
                formatted_block = f"```python\n{formatted_code}\n```"
                formatted_content = formatted_content.replace(
                    original_block,
                    formatted_block,
                    1  # Replace only first occurrence
                )
                
                if __event_emitter__:
                    await __event_emitter__({
                        "type": "status",
                        "data": {
                            "description": f"Formatted {i+1}/{len(code_blocks)} blocks",
                            "done": False
                        }
                    })
            
            # Success
            if __event_emitter__:
                await __event_emitter__({
                    "type": "status",
                    "data": {
                        "description": "Formatting complete",
                        "done": True
                    }
                })
                
                await __event_emitter__({
                    "type": "notification",
                    "data": {
                        "type": "success",
                        "content": f"Formatted {len(code_blocks)} code block(s)"
                    }
                })
            
            return {"content": formatted_content}
        
        except Exception as e:
            if __event_emitter__:
                await __event_emitter__({
                    "type": "notification",
                    "data": {
                        "type": "error",
                        "content": f"Formatting failed: {str(e)}"
                    }
                })
            
            return {"content": content}  # Return original on error
```

## Testing Checklist

- [ ] Action appears in message toolbar
- [ ] Button icon displays correctly
- [ ] Button name is clear
- [ ] Action executes without errors
- [ ] Confirmation dialogs work
- [ ] Input dialogs work
- [ ] Status updates display
- [ ] Notifications appear
- [ ] Error handling works
- [ ] User permissions respected
- [ ] Files processed correctly (if applicable)
- [ ] Performance is acceptable

## Common Pitfalls

1. **Not requesting confirmation** - Ask before destructive operations
2. **No status updates** - Show progress for long operations
3. **Poor error messages** - Provide actionable feedback
4. **Ignoring user permissions** - Check roles when needed
5. **Blocking operations** - Use async for I/O
6. **Missing icon** - Actions look better with custom icons
7. **Not handling cancellation** - Respect when user cancels
8. **Modifying wrong content** - Validate body structure first

## Additional Resources

- [Action Function Documentation](https://docs.openwebui.com/features/plugin/functions/action)
- [Example Actions](https://openwebui.com/search?type=action)
- [Event System Guide](https://docs.openwebui.com/features/plugin/events/)
