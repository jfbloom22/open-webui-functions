"""
title: ElevenLabs TTS
author: Workplace Labs
version: 1.3.0
license: MIT
requirements: aiohttp, pydantic
description: Generate speech and attach a native Open WebUI audio file with preview and download support.
"""

"""Generate audio and attach it through Open WebUI's native Files system.

The MP3 is stored in Open WebUI's configured storage provider, not in the chat
message body. The message receives a normal file attachment, so Open WebUI's
native audio preview and authenticated download route handle files of any
reasonable podcast length.
"""

import asyncio
import html
import json
import random
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Literal

import aiohttp
from pydantic import BaseModel, Field


API_BASE_URL = "https://api.elevenlabs.io/v1"
QUALITY_MODEL = "eleven_multilingual_v2"
FAST_MODEL = "eleven_flash_v2_5"
MODEL_CHARACTER_LIMITS = {
    "eleven_v3": 5000,
    QUALITY_MODEL: 10000,
    FAST_MODEL: 40000,
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
    """Strip presentation markup so the generated speech sounds natural."""
    text = text_from_content(content)
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<https?://[^>]+>", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"(?m)^\s{0,3}(?:#{1,6}|>|[-+*]|\d+[.)])\s+", "", text)
    text = re.sub(r"(?<!\w)[*_~`]+|[*_~`]+(?!\w)", "", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def model_for_mode(mode: str) -> str:
    return FAST_MODEL if mode.strip().casefold() == "fast" else QUALITY_MODEL


def split_speech_text(text: str, max_characters: int) -> list[str]:
    """Split long narration at sentence boundaries within a provider limit."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if not sentence:
            continue
        if len(sentence) > max_characters:
            if current:
                chunks.append(current)
                current = ""
            while len(sentence) > max_characters:
                split_at = sentence.rfind(" ", 0, max_characters + 1)
                split_at = split_at if split_at > 0 else max_characters
                chunks.append(sentence[:split_at].strip())
                sentence = sentence[split_at:].strip()
            if sentence:
                current = sentence
        elif current and len(current) + 1 + len(sentence) <= max_characters:
            current = f"{current} {sentence}"
        else:
            if current:
                chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks or [text.strip()]


def filename_voice_part(voice_name: str) -> str:
    """Keep the friendly filename safe for storage and downloads."""
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", voice_name).strip(".-")
    return value or "voice"


async def upload_audio_file(
    audio: bytes,
    filename: str,
    voice_name: str,
    user: dict,
    request: Any,
) -> dict[str, Any]:
    """Store audio in Open WebUI's configured file storage and return its file card data."""
    user_id = user.get("id") if isinstance(user, dict) else None
    authorization = request.headers.get("Authorization") if request else None
    if not user_id or not authorization or not request:
        raise ValueError("Open WebUI file storage requires an authenticated request.")

    form = aiohttp.FormData()
    form.add_field("file", audio, filename=filename, content_type="audio/mpeg")
    form.add_field(
        "metadata",
        json.dumps({"name": filename, "content_type": "audio/mpeg", "size": len(audio)}),
    )
    origin = request.headers.get("Origin")
    if origin == "null":
        origin = None
    base_url = (origin or str(request.base_url)).rstrip("/")
    headers = {"Authorization": authorization}
    timeout = aiohttp.ClientTimeout(total=max(120, 2 * 90))
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            f"{base_url}/api/v1/files/?process=false&process_in_background=false",
            data=form,
            headers=headers,
        ) as response:
            if response.status >= 400:
                raise ValueError(await Action.api_error(response, "save the audio file"))
            file_record = await response.json()

        file_id = file_record.get("id")
        if not file_id:
            raise ValueError("Open WebUI did not return an audio file ID.")

        note = (
            f"Audio ready with {voice_name}. Select Preview to listen. "
            "To download the MP3, click the filename above."
        )
        async with session.post(
            f"{base_url}/api/v1/files/{file_id}/data/content/update",
            json={"content": note},
            headers={**headers, "Content-Type": "application/json"},
        ) as response:
            if response.status >= 400:
                raise ValueError(await Action.api_error(response, "add the audio download note"))

    return {
        "id": file_id,
        "type": "file",
        "url": file_id,
        "name": filename,
        "size": len(audio),
        "content_type": "audio/mpeg",
    }


def message_result(body: dict, voice_name: str) -> dict[str, Any]:
    """Preserve the answer while explaining where the intentional controls live."""
    current = next(
        (
            message.get("content", "")
            for message in reversed(body.get("messages", []))
            if message.get("role") == "assistant"
        ),
        "",
    ).rstrip()
    notice = f"Audio ready with **{voice_name}**. Open the attached audio file to preview or download it."
    content = f"{current}\n\n{notice}" if current else notice
    if body.get("id"):
        return {"messages": [{"id": body["id"], "content": content}]}
    return {"content": notice}


class Action:
    class Valves(BaseModel):
        ELEVENLABS_API_KEY: str = Field(default="", description="ElevenLabs API key.")
        PLAYBACK_MODE: Literal["quality", "fast"] = Field(
            default="quality",
            description="quality uses Multilingual v2; fast uses Flash v2.5.",
        )
        DEFAULT_VOICE: str = Field(default="Donovan", description="Default curated voice.")
        CUSTOM_VOICES: str = Field(
            default="Donovan:DMyrgzQFny3JI1Y1paM5:Articulate, strong, and deep\nJessica:g6xIsTj2HwM6VR4iXFCw:Friendly and conversational\nMark:1SM7GgM6IMuvQlz2BwM3:Conversational\nArcher:Fahco4VZzobUeiPqni1S:Conversational\nBrittney:kPzsL2i3teMYv0FxEYQ6:Fun, youthful, and informal",
            description="One curated voice per line: Name:VoiceID:optional description.",
        )
        MAX_CHARACTERS: int = Field(
            default=60_000,
            ge=100,
            le=100_000,
            description="Largest total narration input. Long replies are split into provider-sized requests.",
        )
        REQUEST_TIMEOUT_SECONDS: int = Field(default=90, ge=10, le=300)
        RETRY_ATTEMPTS: int = Field(default=2, ge=0, le=4)

    def __init__(self):
        self.valves = self.Valves()

    @staticmethod
    def status(description: str, done: bool = False) -> dict[str, Any]:
        return {"type": "status", "data": {"description": description, "done": done}}

    def selected_model(self) -> str:
        return model_for_mode(self.valves.PLAYBACK_MODE)

    @staticmethod
    def resolve_voice(name: str, voices: dict[str, str]) -> tuple[str, str] | None:
        for candidate, voice_id in voices.items():
            if candidate.casefold() == name.strip().casefold():
                return candidate, voice_id
        return None

    async def voice_options(self) -> tuple[dict[str, str], dict[str, str]]:
        voices, descriptions = parse_custom_voices(self.valves.CUSTOM_VOICES)
        if voices:
            return voices, descriptions
        timeout = aiohttp.ClientTimeout(total=self.valves.REQUEST_TIMEOUT_SECONDS)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                f"{API_BASE_URL}/voices", headers={"xi-api-key": self.valves.ELEVENLABS_API_KEY}
            ) as response:
                if response.status >= 400:
                    raise ValueError(await self.api_error(response, "load voices"))
                data = await response.json()
        return {voice["name"]: voice["voice_id"] for voice in data.get("voices", [])}, {}

    @staticmethod
    async def api_error(response: aiohttp.ClientResponse, operation: str) -> str:
        try:
            payload = await response.json(content_type=None)
            detail = payload.get("detail") or payload.get("message") or str(payload)
        except Exception:
            detail = (await response.text())[:500]
        return f"ElevenLabs could not {operation} (HTTP {response.status}): {detail}"

    @staticmethod
    def retry_delay(attempt: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                return min(30.0, max(0.0, float(retry_after)))
            except ValueError:
                pass
        return random.uniform(0, min(8.0, 0.5 * (2**attempt)))

    async def generate_audio(
        self, voice_id: str, text: str, previous_request_ids: list[str] | None = None
    ) -> tuple[bytes, str | None]:
        headers = {"xi-api-key": self.valves.ELEVENLABS_API_KEY, "Content-Type": "application/json"}
        payload = {
            "text": text,
            "model_id": self.selected_model(),
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.5},
        }
        if previous_request_ids:
            payload["previous_request_ids"] = previous_request_ids[-3:]
        timeout = aiohttp.ClientTimeout(total=self.valves.REQUEST_TIMEOUT_SECONDS)
        for attempt in range(self.valves.RETRY_ATTEMPTS + 1):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        f"{API_BASE_URL}/text-to-speech/{voice_id}",
                        params={"output_format": "mp3_44100_128"},
                        json=payload,
                        headers=headers,
                    ) as response:
                        if response.status < 400:
                            return await response.read(), response.headers.get("request-id")
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
        __request__: Any = None,
    ) -> dict[str, Any]:
        try:
            if not self.valves.ELEVENLABS_API_KEY.strip():
                raise ValueError("ElevenLabs API key is not configured in the function settings.")
            if not __event_call__:
                raise ValueError("This Open WebUI client does not support the voice-selection dialog.")
            raw_message = next(
                (m.get("content") for m in reversed(body.get("messages", [])) if m.get("role") == "assistant"),
                None,
            )
            text = speech_text(raw_message)
            if not text:
                raise ValueError("The latest assistant reply has no narratable text.")
            model_limit = MODEL_CHARACTER_LIMITS.get(self.selected_model(), self.valves.MAX_CHARACTERS)
            if len(text) > self.valves.MAX_CHARACTERS:
                raise ValueError(
                    f"This reply is {len(text):,} characters after cleanup; this action supports {self.valves.MAX_CHARACTERS:,}."
                )
            text_chunks = split_speech_text(text, model_limit)
            if __event_emitter__:
                await __event_emitter__(self.status("Preparing speech"))
            voices, descriptions = await self.voice_options()
            default = self.resolve_voice(self.valves.DEFAULT_VOICE, voices)
            default_name = default[0] if default else next(iter(voices), "")
            if not default_name:
                raise ValueError("No ElevenLabs voices are configured.")
            choices = "\n".join(
                f"• **{name}**" + (f" — {descriptions[name]}" if name in descriptions else "")
                for name in voices
            )
            response = await __event_call__(
                {"type": "input", "data": {"title": "Select ElevenLabs voice", "message": f"Choose a listed voice name:\n\n{choices}", "placeholder": "Voice name", "value": default_name}}
            )
            selected = response if isinstance(response, str) else (response or {}).get("message", "")
            resolved = self.resolve_voice(str(selected), voices)
            if not resolved:
                raise ValueError("Voice selection was cancelled or does not match a curated voice.")
            voice_name, voice_id = resolved
            audio_parts: list[bytes] = []
            request_ids: list[str] = []
            for index, text_chunk in enumerate(text_chunks, start=1):
                if __event_emitter__:
                    suffix = f" ({index}/{len(text_chunks)})" if len(text_chunks) > 1 else ""
                    await __event_emitter__(self.status(f"Generating speech with {voice_name}{suffix}"))
                generated = await self.generate_audio(voice_id, text_chunk, request_ids)
                if isinstance(generated, tuple):
                    audio_part, request_id = generated
                else:  # Keep compatibility with simple test doubles and older runners.
                    audio_part, request_id = generated, None
                audio_parts.append(audio_part)
                if request_id:
                    request_ids.append(request_id)
            audio = b"".join(audio_parts)
            filename = (
                f"Podcast audio - {filename_voice_part(voice_name)} - "
                f"{datetime.now(timezone.utc).strftime('%Y-%m-%d-%H%M%S')} - {uuid.uuid4().hex[:8]}.mp3"
            )
            file_card = await upload_audio_file(audio, filename, voice_name, __user__, __request__)
            if __event_emitter__:
                await __event_emitter__({"type": "files", "data": {"files": [file_card]}})
                await __event_emitter__(self.status("Audio ready", done=True))
            return message_result(body, voice_name)
        except ValueError as exc:
            message = str(exc)
        except Exception:
            message = "Audio generation failed unexpectedly. Please try again or contact an administrator."
        if __event_emitter__:
            await __event_emitter__(self.status("Audio generation failed", done=True))
            await __event_emitter__({"type": "notification", "data": {"type": "error", "content": message}})
        return {"content": message}
