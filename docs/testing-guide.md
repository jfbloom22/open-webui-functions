# Testing Guide for Open WebUI Extensions

Comprehensive testing strategies for Pipes, Filters, Actions, and Tools.

## Table of Contents

- [Testing Principles](#testing-principles)
- [Manual Testing](#manual-testing)
- [Unit Testing](#unit-testing)
- [Integration Testing](#integration-testing)
- [Performance Testing](#performance-testing)
- [Security Testing](#security-testing)
- [Test Checklists](#test-checklists)

## Testing Principles

### Test Early and Often

- Test during development, not just at the end
- Write tests alongside your code
- Run tests before committing changes
- Automate testing where possible

### Test Coverage

Aim for comprehensive coverage of:

- **Happy path**: Normal, expected usage
- **Edge cases**: Boundary conditions, unusual inputs
- **Error conditions**: Invalid inputs, API failures, timeouts
- **Concurrency**: Multiple simultaneous requests
- **Performance**: Response times under load
- **Security**: Input validation, authentication, authorization

### Testing Pyramid

```
       /\
      /  \      Few: End-to-end tests (full Open WebUI integration)
     /----\
    /      \    Some: Integration tests (with mocked APIs)
   /--------\
  /          \  Many: Unit tests (individual functions)
 /____________\
```

## Manual Testing

### Initial Setup Test

Before diving into functionality, verify basic setup:

**Checklist:**
- [ ] Extension loads without Python syntax errors
- [ ] Valves configuration saves and loads correctly
- [ ] Extension appears in appropriate location (model selector, filters, etc.)
- [ ] Icons display correctly (if applicable)
- [ ] Toggle switches work (if applicable)

**Steps:**
1. Install extension in Open WebUI
2. Navigate to Admin Panel → Functions
3. Verify extension appears in list
4. Click to open configuration
5. Modify Valves settings and save
6. Reload page and verify settings persisted

### Testing Pipes

**Test Case 1: Pipe Appears in Model Selector**
1. Enable the Pipe in Admin Panel
2. Navigate to chat interface
3. Open model selector
4. Verify Pipe appears in the list
5. Verify name displays correctly

**Test Case 2: Basic Interaction**
1. Select your Pipe from model selector
2. Send a simple test message: "Hello, how are you?"
3. Verify response is received
4. Check for error messages or console errors

**Test Case 3: Streaming Response**
```
Test message: "Write a short story about a robot."

Expected:
- Response streams word-by-word
- No delays or hanging
- Complete response received
- No errors in console
```

**Test Case 4: Model Selection (for Manifolds)**
```
For Pipes with multiple models:
1. Verify all models appear in selector
2. Select different models
3. Verify correct model is used for each request
4. Check model ID extraction is correct
```

**Test Case 5: Error Handling**
```
Test scenarios:
- Empty API key in Valves
- Invalid API URL
- Network timeout (disconnect internet)
- API rate limit exceeded
- Invalid model ID

Expected for each:
- Clear error message displayed
- No crashes or unhandled exceptions
- User can recover (fix configuration and retry)
```

### Testing Filters

**Test Case 1: Filter Activation**
1. Enable filter globally or for specific model
2. Navigate to model settings
3. Verify filter appears in filter list
4. Enable/disable toggle and verify state persists

**Test Case 2: Inlet Modification**
```
Test scenario:
- Filter adds system context to inputs
- Send message: "What's the weather?"
- Check that context was added (via logs or outlet)

Expected:
- Input modified before reaching model
- Model receives modified input
- Response reflects added context
```

**Test Case 3: Stream Processing**
```
Test scenario:
- Filter modifies streaming chunks
- Send message requiring long response
- Monitor streaming output

Expected:
- Modifications applied to each chunk
- No delays or blocking
- Complete response is modified correctly
```

**Test Case 4: Outlet Modification**
```
Test scenario:
- Filter formats model outputs
- Send message and receive response
- Check output formatting

Expected:
- Output modified after model completion
- Formatting applied correctly
- No content loss or corruption
```

**Test Case 5: Filter Priority**
```
Test scenario (with multiple filters):
1. Set different priorities for filters
2. Send test message
3. Verify execution order via logs

Expected:
- Filters execute in priority order
- Each receives output from previous filter
- Final result includes all modifications
```

### Testing Actions

**Test Case 1: Button Appears**
1. Enable action globally or for specific model
2. Have model generate a message
3. Verify action button appears below message
4. Verify icon and name display correctly

**Test Case 2: Basic Action Execution**
```
Test scenario:
1. Click action button
2. Monitor status updates
3. Verify completion

Expected:
- Action executes without errors
- Status updates appear
- Final result displays correctly
```

**Test Case 3: Confirmation Dialog**
```
Test scenario:
1. Click action button
2. Confirmation dialog appears
3. Test both "Confirm" and "Cancel"

Expected:
- Dialog displays with clear message
- Confirm proceeds with action
- Cancel aborts action cleanly
```

**Test Case 4: Input Dialog**
```
Test scenario:
1. Click action button
2. Input dialog appears
3. Enter test value and submit

Expected:
- Dialog displays with clear prompt
- Input accepted and processed
- Result reflects input value
```

**Test Case 5: Multi-Action**
```
For actions with multiple sub-actions:
1. Verify all action buttons appear
2. Click each action button
3. Verify correct action executes

Expected:
- Each action executes correctly
- No cross-contamination between actions
- All actions work independently
```

### Testing Tools

**Test Case 1: Function Calling**
```
Test scenario:
1. Select model with function calling support
2. Ask question that should trigger tool
3. Monitor tool execution

Example prompt: "Search the web for Python tutorials"

Expected:
- Model decides to call search tool
- Tool executes with correct parameters
- Results returned to model
- Model incorporates results in response
```

**Test Case 2: Parameter Handling**
```
Test different parameter types:
- Required parameters: Verify enforcement
- Optional parameters: Test with/without values
- Default values: Verify defaults applied
- Complex types: Test nested structures

Expected:
- All parameter types handled correctly
- Validation errors caught and reported
- Type coercion works as expected
```

**Test Case 3: Return Value Handling**
```
Test different return scenarios:
- Successful return with data
- Empty results
- Error conditions
- Large data sets

Expected:
- All return types handled correctly
- Model can process returned data
- No serialization errors
```

## Unit Testing

### Setup Test Environment

```python
# tests/conftest.py
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_event_emitter():
    """Mock event emitter for testing."""
    return AsyncMock()

@pytest.fixture
def mock_event_call():
    """Mock event call for testing."""
    async def _call(data):
        if data["type"] == "confirmation":
            return True  # Auto-confirm
        if data["type"] == "input":
            return "test input"
        return None
    return _call

@pytest.fixture
def mock_user():
    """Mock user object."""
    return {
        "id": "test-user-123",
        "name": "Test User",
        "email": "test@example.com",
        "role": "user",
    }
```

### Testing Pipes

```python
# tests/test_pipe.py
import pytest
from unittest.mock import AsyncMock, patch
from my_pipe import Pipe

@pytest.fixture
def pipe():
    p = Pipe()
    p.valves.API_KEY = "test-key"
    return p

@pytest.mark.asyncio
async def test_pipe_basic_request(pipe, mock_event_emitter):
    """Test basic pipe request."""
    body = {
        "messages": [{"role": "user", "content": "Hello"}],
        "model": "test-model",
        "stream": False,
    }
    
    with patch("aiohttp.ClientSession") as mock_session:
        # Mock API response
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hi there!"}}]
        }
        mock_response.raise_for_status = AsyncMock()
        
        mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response
        
        result = await pipe.pipe(body, __event_emitter__=mock_event_emitter)
        
        assert result is not None
        assert "choices" in result

@pytest.mark.asyncio
async def test_pipe_missing_api_key(pipe, mock_event_emitter):
    """Test pipe behavior without API key."""
    pipe.valves.API_KEY = ""
    
    body = {"messages": [], "model": "test"}
    
    result = await pipe.pipe(body, __event_emitter__=mock_event_emitter)
    
    # Should return error
    assert "error" in str(result).lower() or result.get("content")

@pytest.mark.asyncio
async def test_pipe_timeout_handling(pipe):
    """Test timeout handling."""
    import asyncio
    
    pipe.valves.TIMEOUT = 1
    body = {"messages": [], "model": "test"}
    
    with patch("aiohttp.ClientSession") as mock_session:
        # Simulate timeout
        mock_session.return_value.__aenter__.return_value.post.side_effect = asyncio.TimeoutError()
        
        result = await pipe.pipe(body)
        
        # Should handle timeout gracefully
        assert result is not None
```

### Testing Filters

```python
# tests/test_filter.py
import pytest
from my_filter import Filter

@pytest.fixture
def filter_instance():
    return Filter()

@pytest.mark.asyncio
async def test_inlet_adds_context(filter_instance):
    """Test inlet adds context to messages."""
    body = {
        "messages": [
            {"role": "user", "content": "Hello"}
        ]
    }
    
    result = await filter_instance.inlet(body)
    
    # Verify context was added
    assert len(result["messages"]) > 1 or "context" in result["messages"][0]["content"].lower()

@pytest.mark.asyncio
async def test_inlet_empty_messages(filter_instance):
    """Test inlet handles empty messages."""
    body = {"messages": []}
    
    result = await filter_instance.inlet(body)
    
    # Should handle gracefully
    assert result is not None
    assert "messages" in result

def test_stream_modification(filter_instance):
    """Test stream modifies chunks."""
    event = {
        "id": "test",
        "choices": [{
            "delta": {"content": "test content"}
        }]
    }
    
    result = filter_instance.stream(event)
    
    # Verify modification applied
    assert result["choices"][0]["delta"]["content"] != "test content" or result == event

@pytest.mark.asyncio
async def test_outlet_formatting(filter_instance):
    """Test outlet formats output."""
    body = {
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
    }
    
    result = await filter_instance.outlet(body)
    
    # Verify formatting applied
    assert result is not None
    assert "messages" in result
```

### Testing Actions

```python
# tests/test_action.py
import pytest
from my_action import Action

@pytest.fixture
def action():
    a = Action()
    a.valves.API_KEY = "test-key"
    return a

@pytest.mark.asyncio
async def test_action_execution(action, mock_event_emitter, mock_event_call):
    """Test basic action execution."""
    body = {
        "content": "Test message to process",
        "messages": []
    }
    
    result = await action.action(
        body,
        __event_emitter__=mock_event_emitter,
        __event_call__=mock_event_call,
    )
    
    assert result is not None
    assert "content" in result
    
    # Verify event emitter was called
    mock_event_emitter.assert_called()

@pytest.mark.asyncio
async def test_action_user_cancellation(action, mock_event_emitter):
    """Test action cancellation."""
    # Mock cancel response
    async def cancel_call(data):
        return False
    
    body = {"content": "test"}
    
    result = await action.action(
        body,
        __event_call__=cancel_call,
    )
    
    # Should handle cancellation
    assert "cancel" in result.get("content", "").lower() or result is not None

@pytest.mark.asyncio
async def test_action_error_handling(action, mock_event_emitter):
    """Test action error handling."""
    body = {}  # Invalid body
    
    result = await action.action(
        body,
        __event_emitter__=mock_event_emitter,
    )
    
    # Should handle error gracefully
    assert result is not None
```

### Testing Tools

```python
# tests/test_tool.py
import pytest
from my_tool import Tools

@pytest.fixture
def tools():
    t = Tools()
    t.valves.API_KEY = "test-key"
    return t

@pytest.mark.asyncio
async def test_tool_function(tools, mock_event_emitter):
    """Test tool function execution."""
    result = await tools.my_function(
        "test parameter",
        __event_emitter__=mock_event_emitter,
    )
    
    assert result is not None
    assert isinstance(result, str)

@pytest.mark.asyncio
async def test_tool_invalid_input(tools):
    """Test tool handles invalid input."""
    with pytest.raises(ValueError):
        await tools.my_function("")

@pytest.mark.asyncio
async def test_tool_return_type(tools):
    """Test tool returns correct type."""
    result = await tools.my_function("test")
    
    # Verify return type matches type hint
    assert isinstance(result, str)  # or whatever the return type is
```

## Integration Testing

### Testing with Mock APIs

```python
# tests/test_integration.py
import pytest
from aioresponses import aioresponses
from my_pipe import Pipe

@pytest.mark.asyncio
async def test_pipe_with_mock_api():
    """Test pipe with mocked external API."""
    pipe = Pipe()
    pipe.valves.API_KEY = "test-key"
    pipe.valves.API_URL = "https://api.example.com"
    
    with aioresponses() as mock:
        # Mock API endpoint
        mock.post(
            "https://api.example.com/chat/completions",
            payload={
                "choices": [{"message": {"content": "Mocked response"}}]
            },
            status=200,
        )
        
        body = {
            "messages": [{"role": "user", "content": "Hello"}],
            "model": "test-model",
        }
        
        result = await pipe.pipe(body)
        
        assert result is not None
        assert "choices" in result
```

## Performance Testing

### Response Time Testing

```python
import time
import pytest

@pytest.mark.asyncio
async def test_pipe_response_time(pipe):
    """Test pipe responds within acceptable time."""
    body = {"messages": [{"role": "user", "content": "test"}], "model": "test"}
    
    start = time.time()
    await pipe.pipe(body)
    duration = time.time() - start
    
    # Should respond within 5 seconds
    assert duration < 5.0

@pytest.mark.asyncio
async def test_concurrent_requests(pipe):
    """Test handling multiple concurrent requests."""
    import asyncio
    
    bodies = [
        {"messages": [{"role": "user", "content": f"test {i}"}], "model": "test"}
        for i in range(10)
    ]
    
    start = time.time()
    results = await asyncio.gather(*[pipe.pipe(body) for body in bodies])
    duration = time.time() - start
    
    # All requests should complete
    assert len(results) == 10
    # Should handle concurrency efficiently
    assert duration < 10.0  # Adjust based on expected performance
```

## Security Testing

### Input Validation

```python
@pytest.mark.asyncio
async def test_sql_injection_prevention(filter_instance):
    """Test filter prevents SQL injection."""
    malicious_input = "'; DROP TABLE users; --"
    
    body = {
        "messages": [{"role": "user", "content": malicious_input}]
    }
    
    result = await filter_instance.inlet(body)
    
    # Should sanitize or reject malicious input
    content = result["messages"][0]["content"]
    assert "DROP TABLE" not in content or content != malicious_input

@pytest.mark.asyncio
async def test_xss_prevention(filter_instance):
    """Test filter prevents XSS attacks."""
    malicious_input = "<script>alert('XSS')</script>"
    
    body = {
        "messages": [{"role": "user", "content": malicious_input}]
    }
    
    result = await filter_instance.inlet(body)
    
    # Should sanitize script tags
    content = result["messages"][0]["content"]
    assert "<script>" not in content or content != malicious_input
```

### Authentication Testing

```python
@pytest.mark.asyncio
async def test_requires_authentication(action, mock_event_emitter):
    """Test action requires authentication."""
    body = {"content": "test"}
    
    # No user provided
    result = await action.action(body, __user__=None, __event_emitter__=mock_event_emitter)
    
    # Should handle missing user
    assert "auth" in result.get("content", "").lower() or result is not None
```

## Test Checklists

### Pre-Commit Checklist

- [ ] All unit tests pass
- [ ] Code coverage > 80%
- [ ] No linter errors
- [ ] Type hints pass mypy check
- [ ] Manual smoke test completed
- [ ] Documentation updated

### Pre-Release Checklist

- [ ] All tests pass (unit + integration)
- [ ] Performance tests pass
- [ ] Security tests pass
- [ ] Edge cases tested
- [ ] Error handling tested
- [ ] Concurrent request handling tested
- [ ] Manual testing in Open WebUI completed
- [ ] README and examples updated

### Function-Specific Checklists

See individual guides for detailed checklists:
- [Pipes Testing Checklist](pipes-guide.md#testing-checklist)
- [Filters Testing Checklist](filters-guide.md#testing-checklist)
- [Actions Testing Checklist](actions-guide.md#testing-checklist)
- [Tools Testing Checklist](tools-guide.md#testing-checklist)

## Continuous Testing

### Automated Testing

Set up automated testing in CI/CD:

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: pytest tests/ --cov=. --cov-report=xml
      - run: mypy .
      - run: ruff check .
```

## Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [aioresponses (mock aiohttp)](https://github.com/pnuckowski/aioresponses)
- [Testing Best Practices](https://docs.python-guide.org/writing/tests/)
