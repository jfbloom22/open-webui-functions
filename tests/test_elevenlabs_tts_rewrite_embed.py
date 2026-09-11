import importlib.util
from pathlib import Path

import pytest


def load_module():
    path = (
        Path(__file__).parents[1]
        / "functions/actions/elevenlabs_tts_rewrite_embed/main.py"
    )
    spec = importlib.util.spec_from_file_location("elevenlabs_tts_rewrite_embed", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tts = load_module()


def test_embed_is_self_contained_and_has_intentional_player_and_download_controls():
    rendered = tts.embed_html(b"ID3audio", "episode.mp3", "Ada <Friendly>")
    assert "SUQzYXVkaW8=" in rendered
    assert 'id="player" controls' in rendered
    assert 'id="download"' in rendered
    assert "Download MP3" in rendered
    assert "Ada &lt;Friendly&gt;" in rendered
    assert "/api/v1/files/" not in rendered
    assert "iframe:height" in rendered


def test_embed_message_preserves_assistant_answer_and_describes_controls():
    result = tts.message_result(
        {
            "id": "message-1",
            "messages": [
                {"role": "user", "content": "Narrate this"},
                {"role": "assistant", "content": "Original answer."},
            ],
        },
        "Donovan",
    )
    assert result == {
        "messages": [
            {
                "id": "message-1",
                "content": "Original answer.\n\nAudio ready with **Donovan**. Use the player and **Download MP3** button in the audio card.",
            }
        ]
    }


def test_markup_is_cleaned_before_narration():
    assert tts.speech_text("# Hello\n[guide](https://example.com)\n`thanks`") == "Hello guide thanks"


@pytest.mark.asyncio
async def test_action_uses_main_page_player_and_does_not_emit_sandboxed_embed(monkeypatch):
    action = tts.Action()
    action.valves.ELEVENLABS_API_KEY = "test-key"
    action.valves.MAX_EMBED_AUDIO_BYTES = 100_000
    monkeypatch.setattr(action, "voice_options", lambda: async_value(({"Ada": "voice-id"}, {}))
    )
    monkeypatch.setattr(action, "generate_audio", lambda voice_id, text: async_value(b"ID3audio"))
    events = []

    async def emit(event):
        events.append(event)

    async def choose_voice(event):
        assert event["type"] == "input"
        return "Ada"

    result = await action.action(
        {
            "id": "message-1",
            "messages": [{"role": "assistant", "content": "A short answer."}],
        },
        __event_emitter__=emit,
        __event_call__=choose_voice,
    )

    assert not any(event["type"] == "embeds" for event in events)
    execute_event = next(event for event in events if event["type"] == "execute")
    assert "Download MP3" in execute_event["data"]["code"]
    assert "<audio" not in execute_event["data"]["code"]
    assert "createElement('audio')" in execute_event["data"]["code"]
    assert result["messages"][0]["id"] == "message-1"


@pytest.mark.asyncio
async def test_action_rejects_audio_that_would_bloat_chat_history(monkeypatch):
    action = tts.Action()
    action.valves.ELEVENLABS_API_KEY = "test-key"
    action.valves.MAX_EMBED_AUDIO_BYTES = 100_000
    monkeypatch.setattr(action, "voice_options", lambda: async_value(({"Ada": "voice-id"}, {}))
    )
    monkeypatch.setattr(
        action, "generate_audio", lambda voice_id, text: async_value(b"x" * 100_001)
    )

    result = await action.action(
        {"messages": [{"role": "assistant", "content": "A short answer."}]},
        __event_call__=lambda event: async_value("Ada"),
    )
    assert "embedded-player limit" in result["content"]


async def async_value(value):
    return value
