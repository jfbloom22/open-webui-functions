"""Regression tests for the Anthropic manifold's provider-independent logic."""

import asyncio
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from typing import Any


def _install_dependency_stubs() -> None:
    """Install minimal runtime stubs when Open WebUI test dependencies are absent."""
    if "pydantic" not in sys.modules:
        pydantic = types.ModuleType("pydantic")

        class BaseModel:
            """Small subset of Pydantic used by the pipe's valve declarations."""

            def __init__(self, **values: Any) -> None:
                for name, value in self.__class__.__dict__.items():
                    if not name.startswith("_") and not callable(value):
                        setattr(self, name, values.get(name, value))
                for name, value in values.items():
                    setattr(self, name, value)

        def field(default: Any = None, **_: Any) -> Any:
            """Return the declared default value."""
            return default

        pydantic.BaseModel = BaseModel
        pydantic.Field = field
        sys.modules["pydantic"] = pydantic

    if "httpx" not in sys.modules:
        httpx = types.ModuleType("httpx")

        class HTTPError(Exception):
            """Base HTTP error stub."""

        class TransportError(HTTPError):
            """Transport error stub."""

        class HTTPStatusError(HTTPError):
            """HTTP status error stub."""

            def __init__(self, response: Any) -> None:
                self.response = response

        class Timeout:
            """Timeout configuration stub."""

            def __init__(self, *_: Any, **__: Any) -> None:
                pass

        class AsyncClient:
            """Async client annotation stub; HTTP is not exercised by unit tests."""

        httpx.HTTPError = HTTPError
        httpx.TransportError = TransportError
        httpx.HTTPStatusError = HTTPStatusError
        httpx.Timeout = Timeout
        httpx.AsyncClient = AsyncClient
        sys.modules["httpx"] = httpx


_install_dependency_stubs()
MODULE_PATH = Path(__file__).parents[1] / "functions/pipes/anthropic/main.py"
SPEC = importlib.util.spec_from_file_location("anthropic_pipe_under_test", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
Pipe = MODULE.Pipe


class AnthropicPipeTests(unittest.TestCase):
    """Verify Anthropic payload, thinking, and native-tool translation behavior."""

    def setUp(self) -> None:
        """Create a configured pipe for each test."""
        self.pipe = Pipe()
        self.pipe.valves.ANTHROPIC_API_KEY = "test-key"

    def test_adaptive_capabilities_omit_sampling_and_define_native_tools(self) -> None:
        """Use discovered adaptive-thinking capability data instead of sampling defaults."""
        self.pipe.valves.ENABLE_PROMPT_CACHING = True
        self.pipe.valves.PROMPT_CACHE_TTL = "1h"
        self.pipe.valves.EFFORT = "xhigh"
        self.pipe._model_capabilities = {
            "claude-future": {
                "thinking": {"types": {"adaptive": {"supported": True}}},
                "effort": {"high": {"supported": True}, "low": {"supported": True}},
            }
        }

        def weather(location: str, unit: str = "c") -> str:
            """Look up weather for a location."""
            return f"{location}: 20{unit}"

        payload, tools = self.pipe._build_payload(
            {
                "model": "anthropic.claude-future",
                "messages": [
                    {"role": "system", "content": "Stable instructions"},
                    {"role": "user", "content": "What is the weather?"},
                ],
                "temperature": 0.2,
                "top_p": 0.4,
            },
            {"params": {"function_calling": "native"}},
            {"weather": {"callable": weather}},
        )

        self.assertEqual(payload["model"], "claude-future")
        self.assertEqual(payload["thinking"]["type"], "adaptive")
        self.assertEqual(payload["output_config"]["effort"], "high")
        self.assertNotIn("temperature", payload)
        self.assertNotIn("top_p", payload)
        self.assertEqual(payload["system"][0]["cache_control"]["ttl"], "1h")
        self.assertEqual(payload["tools"][0]["name"], "weather")
        self.assertEqual(payload["tools"][0]["input_schema"]["required"], ["location"])
        self.assertIn("weather", tools)

    def test_manual_thinking_preserves_explicit_sampling(self) -> None:
        """Use manual thinking only for model families that still support it."""
        def calculator(expression: str) -> str:
            """Evaluate an expression."""
            return expression

        payload, _ = self.pipe._build_payload(
            {
                "model": "anthropic/claude-sonnet-4-5",
                "messages": [{"role": "user", "content": "Solve this."}],
                "temperature": 0.3,
                "top_k": 10,
                "tool_choice": "required",
            },
            {"params": {"function_calling": "native"}},
            {"calculator": {"callable": calculator}},
        )

        self.assertEqual(payload["thinking"]["type"], "enabled")
        self.assertEqual(payload["temperature"], 0.3)
        self.assertEqual(payload["top_k"], 10)
        self.assertEqual(payload["tool_choice"], {"type": "auto"})

    def test_openai_tool_history_becomes_anthropic_content_blocks(self) -> None:
        """Translate assistant tool calls and tool-role results into Messages API blocks."""
        _, messages = self.pipe._translate_messages(
            [
                {"role": "user", "content": "Check the weather."},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "weather",
                                "arguments": '{"location":"Boston"}',
                            },
                        }
                    ],
                },
                {"role": "tool", "tool_call_id": "call_1", "content": "18 C"},
            ]
        )

        tool_use = messages[1]["content"][-1]
        tool_result = messages[2]["content"][0]
        self.assertEqual(tool_use["type"], "tool_use")
        self.assertEqual(tool_use["input"], {"location": "Boston"})
        self.assertEqual(tool_result["type"], "tool_result")
        self.assertEqual(tool_result["tool_use_id"], "call_1")
        self.assertEqual(messages[2]["role"], "user")

    def test_execute_tools_supports_async_callables_and_errors(self) -> None:
        """Execute injected async callables and return Anthropic-shaped errors."""

        async def add(left: int, right: int) -> int:
            """Add two integers."""
            return left + right

        async def run_test() -> list[dict[str, Any]]:
            return await self.pipe._execute_tools(
                [
                    {"id": "call_1", "name": "add", "input": {"left": 2, "right": 3}},
                    {"id": "call_2", "name": "missing", "input": {}},
                ],
                {"add": add},
                None,
            )

        results = asyncio.run(run_test())
        self.assertEqual(results[0]["content"], "5")
        self.assertTrue(results[1]["is_error"])
        self.assertIn("Unknown tool", results[1]["content"])

    def test_format_response_keeps_thinking_separate_from_text(self) -> None:
        """Render thinking only when the display valve permits it."""
        response = {
            "content": [
                {"type": "thinking", "thinking": "Reasoning"},
                {"type": "text", "text": "Answer"},
            ]
        }
        self.assertEqual(self.pipe._format_response(response), "<think>Reasoning</think>Answer")
        self.pipe.valves.DISPLAY_THINKING = False
        self.assertEqual(self.pipe._format_response(response), "Answer")


if __name__ == "__main__":
    unittest.main()
