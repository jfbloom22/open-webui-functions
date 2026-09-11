import importlib.util
import sys
import types
from types import SimpleNamespace
from pathlib import Path

import pytest


def load_module():
    open_webui = types.ModuleType("open_webui")
    models = types.ModuleType("open_webui.models")
    files = types.ModuleType("open_webui.models.files")
    storage = types.ModuleType("open_webui.storage")
    provider = types.ModuleType("open_webui.storage.provider")
    files.FileForm = dict
    files.Files = object
    provider.Storage = object
    sys.modules.update(
        {
            "open_webui": open_webui,
            "open_webui.models": models,
            "open_webui.models.files": files,
            "open_webui.storage": storage,
            "open_webui.storage.provider": provider,
        }
    )
    path = Path(__file__).parents[1] / "functions/actions/elevenlabs_tts/main.py"
    spec = importlib.util.spec_from_file_location("elevenlabs_tts", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tts = load_module()


def test_parses_curated_voices_and_ignores_malformed_lines():
    voices, descriptions = tts.parse_custom_voices(
        "Ada:id-a:Warm\ninvalid\n :id-b\nLin:id-l"
    )
    assert voices == {"Ada": "id-a", "Lin": "id-l"}
    assert descriptions == {"Ada": "Warm"}


def test_markdown_is_cleaned_for_speech_without_link_urls_or_code():
    result = tts.speech_text(
        "# Hello\n[Read this](https://example.com)\n```python\nprint('no')\n```\n*Final* <b>words</b>"
    )
    assert result == "Hello Read this Final words"


def test_multipart_content_is_supported():
    assert (
        tts.speech_text(
            [{"type": "image_url", "image_url": {}}, {"type": "text", "text": "Hello"}]
        )
        == "Hello"
    )


def test_model_choice_and_character_limits_match_documented_models():
    assert tts.model_for_mode("fast") == "eleven_flash_v2_5"
    assert tts.model_for_mode("QUALITY") == "eleven_multilingual_v2"
    assert tts.MODEL_CHARACTER_LIMITS["eleven_v3"] == 5000
    assert tts.MODEL_CHARACTER_LIMITS["eleven_flash_v2_5"] == 40000


def test_voice_resolution_is_case_insensitive():
    assert tts.Action.resolve_voice("jEsSiCa", {"Jessica": "voice-id"}) == (
        "Jessica",
        "voice-id",
    )
    assert tts.Action.resolve_voice("unknown", {"Jessica": "voice-id"}) is None


def test_retry_delay_honors_a_valid_server_hint_and_bounds_invalid_hints(monkeypatch):
    assert tts.Action.retry_delay(0, "3") == 3.0
    assert tts.Action.retry_delay(0, "60") == 30.0
    monkeypatch.setattr(tts.random, "uniform", lambda start, end: end)
    assert tts.Action.retry_delay(2, "not-a-number") == 2.0


def test_file_attachment_uses_openwebui_downloadable_message_shape():
    attachment = tts.file_attachment("file-1", "tts.mp3", 1234)
    assert attachment == {
        "type": "file",
        "id": "file-1",
        "url": "/api/v1/files/file-1/content?attachment=true",
        "name": "tts.mp3",
        "content_type": "audio/mpeg",
        "size": 1234,
    }


def test_file_content_url_uses_openwebui_authenticated_route():
    assert tts.file_content_url("file-1") == "/api/v1/files/file-1/content"
    assert (
        tts.file_content_url("file-1", attachment=True)
        == "/api/v1/files/file-1/content?attachment=true"
    )


def test_message_result_adds_a_visible_download_link_without_overwriting_content():
    result = tts.message_with_download_link(
        {
            "id": "message-1",
            "messages": [
                {"role": "user", "content": "Read this aloud"},
                {"role": "assistant", "content": "Here is the response."},
            ],
        },
        "Donovan",
        "file-1",
    )
    assert result == {
        "messages": [
            {
                "id": "message-1",
                "content": "Here is the response.\n\n[Download audio](/api/v1/files/file-1/content?attachment=true)",
            }
        ]
    }


@pytest.mark.asyncio
async def test_create_file_uses_current_async_openwebui_file_api(monkeypatch):
    class Files:
        @staticmethod
        async def insert_new_file(user_id, form):
            assert user_id == "user-1"
            assert form["meta"]["content_type"] == "audio/mpeg"
            assert form["data"]["content"].startswith("Generated audio.")
            return SimpleNamespace(id=form["id"])

    monkeypatch.setattr(tts, "Files", Files)
    monkeypatch.setattr(tts, "FileForm", lambda **data: data)
    monkeypatch.setattr(
        tts,
        "Storage",
        SimpleNamespace(
            upload_file=lambda file, filename, tags: (file.read(), f"/tmp/{filename}")
        ),
    )
    assert await tts.Action.create_file("test.mp3", b"audio", {"id": "user-1"})
