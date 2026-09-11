import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

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
    sys.modules.update({
        "open_webui": open_webui,
        "open_webui.models": models,
        "open_webui.models.files": files,
        "open_webui.storage": storage,
        "open_webui.storage.provider": provider,
    })
    path = Path(__file__).parents[1] / "functions/actions/elevenlabs_tts_rewrite_native/main.py"
    spec = importlib.util.spec_from_file_location("elevenlabs_tts_rewrite_native", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


tts = load_module()


def test_attachment_uses_the_stock_openwebui_file_shape():
    assert tts.attachment("file-1", "audio.mp3", 128) == {
        "type": "file",
        "id": "file-1",
        "name": "audio.mp3",
        "url": "/api/v1/files/file-1/content?attachment=true",
        "content_type": "audio/mpeg",
        "size": 128,
    }


def test_completion_keeps_original_reply_and_adds_named_download_affordance():
    result = tts.completion(
        {"id": "message-1", "messages": [{"role": "assistant", "content": "Hello there."}]},
        "Jessica",
        "file-1",
    )
    content = result["messages"][0]["content"]
    assert content.startswith("Hello there.")
    assert "[Download MP3](/api/v1/files/file-1/content?attachment=true)" in content
    assert "attached MP3" in content


def test_clean_speech_handles_markdown_and_multipart_responses():
    assert tts.clean_speech([{"type": "image_url"}, {"type": "text", "text": "# [Hello](https://example.test)"}]) == "Hello"


def test_voice_parser_and_default_resolution_are_safe():
    voices, descriptions = tts.parse_voices("Ada:id-a:Warm\nbad\nLin:id-l")
    assert voices == {"Ada": "id-a", "Lin": "id-l"}
    assert descriptions == {"Ada": "Warm"}
    assert tts.find_voice("lin", voices) == ("Lin", "id-l")


@pytest.mark.asyncio
async def test_save_audio_populates_binary_file_content_explanation(monkeypatch):
    captured = {}

    class FakeFiles:
        @staticmethod
        async def insert_new_file(user_id, form):
            captured["user_id"] = user_id
            captured["form"] = form
            return SimpleNamespace(id=form["id"])

    monkeypatch.setattr(tts, "Files", FakeFiles)
    monkeypatch.setattr(tts, "FileForm", lambda **data: data)
    monkeypatch.setattr(tts, "Storage", SimpleNamespace(upload_file=lambda file, filename, tags: (file.read(), f"/tmp/{filename}")))
    assert await tts.Action.save_audio("audio.mp3", b"ID3", {"id": "user-1"})
    assert captured["user_id"] == "user-1"
    assert captured["form"]["data"]["content"].startswith("This is an MP3")
    assert captured["form"]["meta"]["content_type"] == "audio/mpeg"
