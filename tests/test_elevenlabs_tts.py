import importlib.util
from pathlib import Path

import pytest


def load_module():
    path = (
        Path(__file__).parents[1]
        / "functions/actions/elevenlabs_tts/main.py"
    )
    spec = importlib.util.spec_from_file_location("elevenlabs_tts", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tts = load_module()


def test_file_message_preserves_assistant_answer_and_describes_controls():
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
                "content": "Original answer.\n\nAudio ready with **Donovan**. Open the attached audio file to preview or download it.",
            }
        ]
    }


def test_markup_is_cleaned_before_narration():
    assert tts.speech_text("# Hello\n[guide](https://example.com)\n`thanks`") == "Hello guide thanks"


def test_voice_filename_part_is_safe_and_friendly():
    assert tts.filename_voice_part("Ada / Friendly") == "Ada-Friendly"
    assert tts.filename_voice_part("...") == "voice"


def test_long_narration_is_split_at_sentence_boundaries():
    chunks = tts.split_speech_text("One two. Three four! Five six?", 12)
    assert chunks == ["One two.", "Three four!", "Five six?"]


@pytest.mark.asyncio
async def test_action_attaches_one_native_audio_file(monkeypatch):
    action = tts.Action()
    action.valves.ELEVENLABS_API_KEY = "test-key"
    monkeypatch.setattr(action, "voice_options", lambda: async_value(({"Ada": "voice-id"}, {}))
    )
    monkeypatch.setattr(action, "generate_audio", lambda voice_id, text: async_value(b"ID3audio"))
    monkeypatch.setattr(
        tts,
        "upload_audio_file",
        lambda audio, filename, voice_name, user, request: async_value(
            {
                "id": "file-1",
                "type": "file",
                "url": "file-1",
                "name": filename,
                "size": len(audio),
                "content_type": "audio/mpeg",
            }
        ),
    )
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

    file_event = next(event for event in events if event["type"] == "files")
    assert file_event["data"]["files"][0]["id"] == "file-1"
    assert file_event["data"]["files"][0]["content_type"] == "audio/mpeg"
    assert not any(event["type"] == "embeds" for event in events)
    assert not any(event["type"] == "execute" for event in events)
    assert result["messages"][0]["id"] == "message-1"


@pytest.mark.asyncio
async def test_action_allows_large_audio_when_file_storage_succeeds(monkeypatch):
    action = tts.Action()
    action.valves.ELEVENLABS_API_KEY = "test-key"
    monkeypatch.setattr(action, "voice_options", lambda: async_value(({"Ada": "voice-id"}, {}))
    )
    monkeypatch.setattr(
        action, "generate_audio", lambda voice_id, text: async_value(b"x" * 100_001)
    )
    monkeypatch.setattr(
        tts,
        "upload_audio_file",
        lambda audio, filename, voice_name, user, request: async_value({"id": "large-file", "type": "file", "url": "large-file", "name": filename, "size": len(audio), "content_type": "audio/mpeg"}),
    )

    result = await action.action(
        {"messages": [{"role": "assistant", "content": "A short answer."}]},
        __event_call__=lambda event: async_value("Ada"),
    )
    assert result["content"].endswith("Open the attached audio file to preview or download it.")


async def async_value(value):
    return value
