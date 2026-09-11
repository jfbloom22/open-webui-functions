"""
title: ElevenLabs TTS
author: Workplace Labs
version: 0.3.3
license: MIT
requirements: aiohttp, pydantic
description: Generate private, downloadable speech from the latest assistant reply with curated ElevenLabs voices.
"""

import asyncio
import html
import io
import random
import re
import uuid
from typing import Any, Callable, Literal

import aiohttp
from pydantic import BaseModel, Field
from open_webui.models.files import FileForm, Files
from open_webui.storage.provider import Storage


API_BASE_URL = "https://api.elevenlabs.io/v1"
QUALITY_MODEL = "eleven_multilingual_v2"
FAST_MODEL = "eleven_flash_v2_5"
MODEL_CHARACTER_LIMITS = {
    "eleven_v3": 5000,
    QUALITY_MODEL: 10000,
    FAST_MODEL: 40000,
    "eleven_flash_v2": 30000,
}


def parse_custom_voices(value: str | None) -> tuple[dict[str, str], dict[str, str]]:
    """Parse Valve lines: display name:voice id:optional description."""
    voices: dict[str, str] = {}
    descriptions: dict[str, str] = {}
    for raw_line in (value or "").splitlines():
        parts = raw_line.split(":", 2)
        if len(parts) < 2:
            continue
        name, voice_id = parts[0].strip(), parts[1].strip()
        if not name or not voice_id:
            continue
        voices[name] = voice_id
        if len(parts) == 3 and parts[2].strip():
            descriptions[name] = parts[2].strip()
    return voices, descriptions


def text_from_content(content: Any) -> str:
    """Return text from either a normal or OpenAI-style multipart message."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") in {"text", "input_text"}
        )
    return ""


def speech_text(content: Any) -> str:
    """Make a readable assistant response suitable for narration, not markup recitation."""
    text = text_from_content(content)
    text = re.sub(r"```[\s\S]*?```", "", text)  # Code is rarely useful when narrated.
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<https?://[^>]+>", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"(?m)^\s{0,3}(?:#{1,6}|>|[-+*]|\d+[.)])\s+", "", text)
    text = re.sub(r"(?<!\w)[*_~`]+|[*_~`]+(?!\w)", "", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def model_for_mode(mode: str) -> str:
    return FAST_MODEL if mode.strip().lower() == "fast" else QUALITY_MODEL


def file_content_url(file_id: str, *, attachment: bool = False) -> str:
    """Return Open WebUI's authenticated file-content route for a stored file."""
    suffix = "?attachment=true" if attachment else ""
    return f"/api/v1/files/{file_id}/content{suffix}"


def file_attachment(file_id: str, filename: str, size: int) -> dict[str, Any]:
    """Shape a generated file for Open WebUI's native file event."""
    return {
        "type": "file",
        "id": file_id,
        "url": file_content_url(file_id, attachment=True),
        "name": filename,
        "content_type": "audio/mpeg",
        "size": size,
    }


class Action:
    class Valves(BaseModel):
        ELEVENLABS_API_KEY: str = Field(default="", description="ElevenLabs API key.")
        PLAYBACK_MODE: Literal["quality", "fast"] = Field(
            default="quality",
            description="quality uses Multilingual v2 for reliable narration; fast uses Flash v2.5 for lower latency.",
        )
        DEFAULT_VOICE: str = Field(
            default="Donovan", description="Default curated voice name."
        )
        CUSTOM_VOICES: str = Field(
            default="Donovan:DMyrgzQFny3JI1Y1paM5:Articulate, strong, and deep\nJessica:g6xIsTj2HwM6VR4iXFCw:Friendly and conversational\nMark:1SM7GgM6IMuvQlz2BwM3:Conversational\nArcher:Fahco4VZzobUeiPqni1S:Conversational\nBrittney:kPzsL2i3teMYv0FxEYQ6:Fun, youthful, and informal",
            description="One curated voice per line: Name:VoiceID:optional description.",
        )
        MAX_CHARACTERS: int = Field(
            default=9000,
            ge=100,
            le=40000,
            description="Maximum speech-ready characters per request.",
        )
        REQUEST_TIMEOUT_SECONDS: int = Field(
            default=90, ge=10, le=300, description="Request timeout."
        )
        RETRY_ATTEMPTS: int = Field(
            default=2,
            ge=0,
            le=4,
            description="Retries for rate-limit and server errors.",
        )

    def __init__(self):
        self.valves = self.Valves()

    @staticmethod
    def status(description: str, done: bool = False) -> dict[str, Any]:
        return {"type": "status", "data": {"description": description, "done": done}}

    def selected_model(self) -> str:
        return model_for_mode(self.valves.PLAYBACK_MODE)

    async def voice_options(self) -> tuple[dict[str, str], dict[str, str]]:
        voices, descriptions = parse_custom_voices(self.valves.CUSTOM_VOICES)
        if voices:
            return voices, descriptions
        headers = {"xi-api-key": self.valves.ELEVENLABS_API_KEY}
        timeout = aiohttp.ClientTimeout(total=self.valves.REQUEST_TIMEOUT_SECONDS)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                f"{API_BASE_URL}/voices", headers=headers
            ) as response:
                if response.status >= 400:
                    raise ValueError(await self.api_error(response, "load voices"))
                data = await response.json()
        return (
            {voice["name"]: voice["voice_id"] for voice in data.get("voices", [])},
            {},
        )

    @staticmethod
    async def api_error(response: aiohttp.ClientResponse, operation: str) -> str:
        try:
            payload = await response.json(content_type=None)
            detail = payload.get("detail") or payload.get("message") or str(payload)
        except Exception:
            detail = (await response.text())[:500]
        return f"ElevenLabs could not {operation} (HTTP {response.status}): {detail}"

    @staticmethod
    def resolve_voice(name: str, voices: dict[str, str]) -> tuple[str, str] | None:
        for candidate, voice_id in voices.items():
            if candidate.casefold() == name.strip().casefold():
                return candidate, voice_id
        return None

    @staticmethod
    def retry_delay(attempt: int, retry_after: str | None) -> float:
        """Respect a server retry hint, otherwise use capped exponential full jitter."""
        if retry_after:
            try:
                return min(30.0, max(0.0, float(retry_after)))
            except ValueError:
                pass
        return random.uniform(0, min(8.0, 0.5 * (2**attempt)))

    async def generate_audio(self, voice_id: str, text: str) -> bytes:
        model_id = self.selected_model()
        payload = {
            "text": text,
            "model_id": model_id,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.5},
        }
        headers = {
            "xi-api-key": self.valves.ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
        }
        timeout = aiohttp.ClientTimeout(total=self.valves.REQUEST_TIMEOUT_SECONDS)
        url = f"{API_BASE_URL}/text-to-speech/{voice_id}"
        for attempt in range(self.valves.RETRY_ATTEMPTS + 1):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        url,
                        params={"output_format": "mp3_44100_128"},
                        json=payload,
                        headers=headers,
                    ) as response:
                        if response.status < 400:
                            return await response.read()
                        error = await self.api_error(response, "generate speech")
                        retryable = response.status == 429 or response.status >= 500
                        retry_after = response.headers.get("Retry-After")
                if not retryable or attempt == self.valves.RETRY_ATTEMPTS:
                    raise ValueError(error)
            except aiohttp.ClientError as exc:
                if attempt == self.valves.RETRY_ATTEMPTS:
                    raise ValueError(f"ElevenLabs connection failed: {exc}") from exc
                retry_after = None
            await asyncio.sleep(self.retry_delay(attempt, retry_after))
        raise ValueError("ElevenLabs could not generate speech.")

    async def action(
        self,
        body: dict,
        __user__: dict = {},
        __event_emitter__: Callable | None = None,
        __event_call__: Callable | None = None,
    ) -> dict[str, Any]:
        try:
            if not self.valves.ELEVENLABS_API_KEY.strip():
                raise ValueError(
                    "ElevenLabs API key is not configured in the function settings."
                )
            if not __user__.get("id"):
                raise ValueError(
                    "You must be signed in to generate a private audio file."
                )
            if not __event_call__:
                raise ValueError(
                    "This Open WebUI client does not support the voice-selection dialog."
                )
            raw_message = next(
                (
                    m.get("content")
                    for m in reversed(body.get("messages", []))
                    if m.get("role") == "assistant"
                ),
                None,
            )
            text = speech_text(raw_message)
            if not text:
                raise ValueError("The latest assistant reply has no narratable text.")
            model_limit = MODEL_CHARACTER_LIMITS.get(
                self.selected_model(), self.valves.MAX_CHARACTERS
            )
            limit = min(self.valves.MAX_CHARACTERS, model_limit)
            if len(text) > limit:
                raise ValueError(
                    f"This reply is {len(text):,} characters after cleanup; the configured limit is {limit:,}."
                )
            if __event_emitter__:
                await __event_emitter__(self.status("Preparing speech"))
            voices, descriptions = await self.voice_options()
            if not voices:
                raise ValueError(
                    "No ElevenLabs voices are available. Add curated voices in function settings."
                )
            default = self.resolve_voice(self.valves.DEFAULT_VOICE, voices)
            default_name = default[0] if default else next(iter(voices))
            choices = "\n".join(
                f"• **{name}**"
                + (f" — {descriptions[name]}" if name in descriptions else "")
                for name in voices
            )
            response = await __event_call__(
                {
                    "type": "input",
                    "data": {
                        "title": "Select ElevenLabs voice",
                        "message": f"Choose a listed voice name:\n\n{choices}",
                        "placeholder": "Voice name",
                        "value": default_name,
                    },
                }
            )
            selected = (
                response
                if isinstance(response, str)
                else (response or {}).get("message", "")
            )
            resolved = self.resolve_voice(str(selected), voices)
            if not resolved:
                raise ValueError(
                    "Voice selection was cancelled or does not match a curated voice."
                )
            voice_name, voice_id = resolved
            if __event_emitter__:
                await __event_emitter__(
                    self.status(
                        f"Generating {self.valves.PLAYBACK_MODE.lower()} speech with {voice_name}"
                    )
                )
            audio = await self.generate_audio(voice_id, text)
            filename = f"tts_{uuid.uuid4()}.mp3"
            file_id = await self.create_file(filename, audio, __user__)
            if not file_id:
                raise ValueError(
                    "Audio was generated but could not be saved to your private files."
                )
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "chat:message:files",
                        "data": {
                            "files": [file_attachment(file_id, filename, len(audio))]
                        },
                    }
                )
                await __event_emitter__(self.status("Audio generated", done=True))
            return {
                "content": (
                    f"Audio generated with ElevenLabs voice **{voice_name}**. "
                    f"[Download the MP3]({file_content_url(file_id, attachment=True)})"
                )
            }
        except ValueError as exc:
            message = str(exc)
        except Exception:
            message = "Audio generation failed unexpectedly. Please try again or contact an administrator."
        if __event_emitter__:
            await __event_emitter__(self.status("Audio generation failed", done=True))
            await __event_emitter__(
                {"type": "notification", "data": {"type": "error", "content": message}}
            )
        return {"content": message}

    @staticmethod
    async def create_file(filename: str, content: bytes, user: dict) -> str | None:
        try:
            file_id = str(uuid.uuid4())
            contents, path = await asyncio.to_thread(
                Storage.upload_file, io.BytesIO(content), f"{file_id}_{filename}", {}
            )
            item = await Files.insert_new_file(
                user["id"],
                FileForm(
                    **{
                        "id": file_id,
                        "filename": filename,
                        "path": path,
                        "meta": {
                            "name": filename,
                            "content_type": "audio/mpeg",
                            "size": len(contents),
                            "data": {"title": "Generated ElevenLabs Audio"},
                        },
                    }
                ),
            )
            return item.id
        except Exception:
            return None
