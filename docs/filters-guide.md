# Filters Development Guide

Filters modify data before it's sent to the LLM (inlet), during streaming (stream), or after it returns (outlet). Use Filters to transform inputs, process outputs, or add automatic context.

## When to Use Filters

Use a Filter when you want to:

- Modify user inputs before sending to the model (inlet)
- Process streaming responses in real-time (stream)  
- Clean up or format model outputs (outlet)
- Add automatic context or instructions
- Implement content moderation
- Log conversations
- Inject dynamic data based on context

## Filter Types

### 1. Always-On Filters

Filters without `self.toggle` run automatically whenever active:

```python
class Filter:
    def __init__(self):
        self.valves = self.Valves()
        # No toggle - always on when enabled
    
    async def inlet(self, body: dict) -> dict:
        """Always runs for this model."""
        # Modify input
        return body
```

**Use cases:**
- Content moderation (always filter)
- PII scrubbing (always remove sensitive data)
- System-level transformations
- Mandatory logging

### 2. Toggleable Filters

Filters with `self.toggle = True` can be enabled/disabled by users:

```python
class Filter:
    def __init__(self):
        self.valves = self.Valves()
        self.toggle = True  # User can toggle on/off
        self.icon = "data:image/svg+xml;base64,..."  # Optional icon
    
    async def inlet(self, body: dict, __event_emitter__=None) -> dict:
        """Runs only when user enables the filter."""
        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {"description": "Filter active", "done": True}
            })
        return body
```

**Use cases:**
- Web search integration (optional)
- Citation mode (user choice)
- Verbose output mode
- Translation filters

## Filter Functions

### inlet() - Pre-Process Inputs

Modifies user input before sending to the model:

```python
async def inlet(
    self,
    body: dict,
    __user__: dict | None = None,
    __event_emitter__: Callable | None = None,
) -> dict:
    """
    Modify input before sending to model.
    
    Args:
        body: Request body with messages
        __user__: User information
        __event_emitter__: For sending status updates
    
    Returns:
        Modified body dict
    """
    # Get last user message
    if body.get("messages"):
        last_message = body["messages"][-1]
        
        # Add context to user input
        if last_message.get("role") == "user":
            last_message["content"] = f"Context: {context}\n\n{last_message['content']}"
    
    return body
```

**Common use cases:**

```python
# Add system context
async def inlet(self, body: dict) -> dict:
    system_msg = {
        "role": "system",
        "content": "You are a helpful coding assistant."
    }
    body["messages"].insert(0, system_msg)
    return body

# Sanitize input
async def inlet(self, body: dict) -> dict:
    if body.get("messages"):
        last_msg = body["messages"][-1]
        # Remove potentially harmful content
        last_msg["content"] = self.sanitize(last_msg["content"])
    return body

# Add automatic instructions
async def inlet(self, body: dict) -> dict:
    if body.get("messages"):
        last_msg = body["messages"][-1]
        last_msg["content"] += "\n\nPlease provide sources for your claims."
    return body
```

### stream() - Process Streaming Responses

Intercepts and modifies streaming chunks in real-time:

```python
def stream(self, event: dict) -> dict:
    """
    Modify streamed response chunks.
    
    Args:
        event: Streaming event with delta content
    
    Returns:
        Modified event dict
    """
    # Process each streamed chunk
    for choice in event.get("choices", []):
        delta = choice.get("delta", {})
        
        if "content" in delta:
            # Modify content in real-time
            delta["content"] = self.transform(delta["content"])
    
    return event
```

**Example stream events:**

```python
# Event structure
{
    "id": "chatcmpl-123",
    "choices": [{
        "delta": {"content": "Hello"}
    }]
}
```

**Common use cases:**

```python
# Filter emojis from stream
def stream(self, event: dict) -> dict:
    for choice in event.get("choices", []):
        delta = choice.get("delta", {})
        if "content" in delta:
            delta["content"] = delta["content"].replace("😊", "")
    return event

# Add formatting to stream
def stream(self, event: dict) -> dict:
    for choice in event.get("choices", []):
        delta = choice.get("delta", {})
        if "content" in delta:
            # Make output bold
            delta["content"] = f"**{delta['content']}**"
    return event

# Log streaming content
def stream(self, event: dict) -> dict:
    for choice in event.get("choices", []):
        delta = choice.get("delta", {})
        if "content" in delta:
            self.logger.debug(f"Streamed: {delta['content']}")
    return event
```

### outlet() - Post-Process Outputs

Modifies complete model response before displaying to user:

```python
async def outlet(
    self,
    body: dict,
    __user__: dict | None = None,
    __event_emitter__: Callable | None = None,
) -> dict:
    """
    Modify output after model completes.
    
    Args:
        body: Complete conversation with model response
        __user__: User information
        __event_emitter__: For sending notifications
    
    Returns:
        Modified body dict
    """
    # Process all messages
    for message in body.get("messages", []):
        if message.get("role") == "assistant":
            # Modify assistant responses
            message["content"] = self.format_output(message["content"])
    
    return body
```

**Common use cases:**

```python
# Redact sensitive info
async def outlet(self, body: dict) -> dict:
    for message in body.get("messages", []):
        message["content"] = message["content"].replace("<<API_KEY>>", "[REDACTED]")
    return body

# Add citations
async def outlet(self, body: dict) -> dict:
    for message in body.get("messages", []):
        if message.get("role") == "assistant":
            message["content"] += "\n\n*Source: Knowledge Base*"
    return body

# Format code blocks
async def outlet(self, body: dict) -> dict:
    for message in body.get("messages", []):
        if message.get("role") == "assistant":
            # Add syntax highlighting hints
            message["content"] = self.format_code_blocks(message["content"])
    return body
```

## Complete Filter Example: Context Injector

```python
"""
title: Context Injection Filter
author: Open WebUI Team
version: 1.0.0
required_open_webui_version: 0.4.0
description: Automatically inject context based on user profile and conversation history
"""

from pydantic import BaseModel, Field
from typing import Callable, Any
import logging

logger = logging.getLogger(__name__)

class Filter:
    class Valves(BaseModel):
        priority: int = Field(
            default=0,
            description="Filter execution priority (lower = earlier)"
        )
        max_context_length: int = Field(
            default=2000,
            ge=100,
            le=10000,
            description="Maximum context length to inject"
        )
        include_user_info: bool = Field(
            default=True,
            description="Include user information in context"
        )
    
    def __init__(self):
        self.valves = self.Valves()
        self.toggle = True  # User can enable/disable
        self.icon = """data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIGZpbGw9Im5vbmUiIHZpZXdCb3g9IjAgMCAyNCAyNCIgc3Ryb2tlPSJjdXJyZW50Q29sb3IiPjxwYXRoIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgc3Ryb2tlLXdpZHRoPSIyIiBkPSJNOSA1SDdDNS44OTU0MyA1IDUgNS44OTU0MyA1IDdWMTlDNSAyMC4xMDQ2IDUuODk1NDMgMjEgNyAyMUgxN0MxOC4xMDQ2IDIxIDE5IDIwLjEwNDYgMTkgMTlWN0MxOSA1Ljg5NTQzIDE4LjEwNDYgNSAxNyA1SDE1TTkgNUMxMCA1IDExIDUgMTEgNUwxMyA1QzEzIDUgMTQgNSAxNSA1TTkgNVY3SDEzVjVNOSAxMUgxNU05IDE1SDEzIi8+PC9zdmc+"""
    
    async def inlet(
        self,
        body: dict,
        __user__: dict | None = None,
        __event_emitter__: Callable[[dict], Any] | None = None,
    ) -> dict:
        """Inject context into user input."""
        try:
            if __event_emitter__:
                await __event_emitter__({
                    "type": "status",
                    "data": {
                        "description": "Injecting context...",
                        "done": False
                    }
                })
            
            # Build context
            context_parts = []
            
            # Add user info if enabled
            if self.valves.include_user_info and __user__:
                user_context = f"User: {__user__.get('name', 'Unknown')}"
                if __user__.get("role"):
                    user_context += f" (Role: {__user__['role']})"
                context_parts.append(user_context)
            
            # Add conversation metadata
            messages = body.get("messages", [])
            if messages:
                context_parts.append(f"Messages in conversation: {len(messages)}")
            
            # Combine context
            context = " | ".join(context_parts)
            
            # Truncate if too long
            if len(context) > self.valves.max_context_length:
                context = context[:self.valves.max_context_length] + "..."
            
            # Inject context as system message
            if context and messages:
                system_msg = {
                    "role": "system",
                    "content": f"[Context: {context}]"
                }
                
                # Insert after any existing system messages
                insert_idx = 0
                for i, msg in enumerate(messages):
                    if msg.get("role") == "system":
                        insert_idx = i + 1
                    else:
                        break
                
                messages.insert(insert_idx, system_msg)
                body["messages"] = messages
            
            if __event_emitter__:
                await __event_emitter__({
                    "type": "status",
                    "data": {
                        "description": "Context injected",
                        "done": True
                    }
                })
            
            return body
            
        except Exception as e:
            logger.error(f"Context injection failed: {e}", exc_info=True)
            
            if __event_emitter__:
                await __event_emitter__({
                    "type": "notification",
                    "data": {
                        "type": "error",
                        "content": f"Context injection failed: {str(e)}"
                    }
                })
            
            # Return original body on error
            return body
    
    def stream(self, event: dict) -> dict:
        """Pass through streaming events unchanged."""
        return event
    
    async def outlet(
        self,
        body: dict,
        __user__: dict | None = None,
        __event_emitter__: Callable | None = None,
    ) -> dict:
        """Pass through output unchanged."""
        return body
```

## Filter Priority and Execution Order

Filters execute in priority order (lower priority = earlier execution):

```python
class Valves(BaseModel):
    priority: int = Field(
        default=0,
        description="Execution priority. Lower runs first."
    )
```

**Execution flow:**
```
Priority 0: Authentication Filter (runs first)
Priority 1: Context Injection Filter
Priority 2: Content Moderation Filter
Priority 3: Logging Filter (runs last)
```

**Important:** Always return the body! Each filter receives the output from the previous filter.

## Global vs Model-Specific Filters

### Global Filters

Apply to all models automatically:

1. Admin Panel → Functions → Filter
2. Click three-dot menu (⋮)
3. Toggle Globe icon (🌐)
4. Ensure filter is Active (green toggle)

**Use for:**
- Security filters (PII scrubbing)
- Compliance requirements
- System-wide logging
- Organization policies

### Model-Specific Filters

Apply only to specific models:

1. Model Settings → Filters
2. Select filters in "Filters" section
3. Set defaults in "Default Filters" section (for toggleable filters)

**Use for:**
- Model-specific formatting
- Specialized context injection
- Optional enhancements

## Common Patterns

### Content Moderation

```python
import re

class Filter:
    def __init__(self):
        self.valves = self.Valves()
        self.banned_patterns = [
            r'\b(offensive|word|here)\b',
            # Add patterns
        ]
    
    async def inlet(self, body: dict, __event_emitter__=None) -> dict:
        """Filter user input for banned content."""
        if body.get("messages"):
            last_msg = body["messages"][-1]
            content = last_msg.get("content", "")
            
            # Check for banned patterns
            for pattern in self.banned_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    if __event_emitter__:
                        await __event_emitter__({
                            "type": "notification",
                            "data": {
                                "type": "error",
                                "content": "Message contains inappropriate content"
                            }
                        })
                    # Replace with safe message
                    last_msg["content"] = "[Content filtered]"
                    break
        
        return body
```

### Automatic Translation

```python
from googletrans import Translator

class Filter:
    def __init__(self):
        self.valves = self.Valves()
        self.toggle = True
        self.translator = Translator()
    
    async def inlet(self, body: dict) -> dict:
        """Translate input to English."""
        if body.get("messages"):
            last_msg = body["messages"][-1]
            content = last_msg["content"]
            
            # Detect and translate
            detection = self.translator.detect(content)
            if detection.lang != "en":
                translated = self.translator.translate(content, dest="en")
                last_msg["content"] = translated.text
        
        return body
    
    async def outlet(self, body: dict) -> dict:
        """Translate output back to original language."""
        # Implementation here
        return body
```

### Conversation Logging

```python
import logging
from datetime import datetime

class Filter:
    def __init__(self):
        self.valves = self.Valves()
        self.logger = logging.getLogger(__name__)
    
    async def inlet(self, body: dict, __user__=None) -> dict:
        """Log user inputs."""
        if body.get("messages"):
            last_msg = body["messages"][-1]
            self.logger.info(
                f"[{datetime.now()}] User {__user__.get('id')}: {last_msg['content']}"
            )
        return body
    
    async def outlet(self, body: dict) -> dict:
        """Log model outputs."""
        for msg in body.get("messages", []):
            if msg.get("role") == "assistant":
                self.logger.info(
                    f"[{datetime.now()}] Assistant: {msg['content'][:100]}..."
                )
        return body
```

## Testing Checklist

- [ ] Filter appears in admin panel
- [ ] Can be enabled/disabled
- [ ] Toggle switch works (if toggleable)
- [ ] Custom icon displays (if set)
- [ ] Priority order is correct
- [ ] inlet modifies input correctly
- [ ] stream processes chunks correctly
- [ ] outlet modifies output correctly
- [ ] Event emitters send notifications
- [ ] Error handling works
- [ ] Doesn't break other filters
- [ ] Performance is acceptable

## Common Pitfalls

1. **Forgetting to return body** - Always return the modified body
2. **Modifying wrong message** - Check message role before editing
3. **Breaking message structure** - Preserve message format
4. **Blocking operations** - Use async for I/O operations
5. **No error handling** - Always use try-except
6. **Ignoring priority** - Set appropriate priority value
7. **Not checking for None** - Validate __user__, __event_emitter__, etc.
8. **Over-processing** - Keep filters lightweight and fast

## Additional Resources

- [Filter Function Documentation](https://docs.openwebui.com/features/plugin/functions/filter)
- [Example Filters](https://openwebui.com/search?type=filter)
- [Event System Guide](https://docs.openwebui.com/features/plugin/events/)
