"""
title: ElevenLabs TTS (Native Attachment)
author: Workplace Labs
version: 1.1.0
license: MIT
requirements: aiohttp, pydantic
description: Generate an ElevenLabs MP3 as a persistent native Open WebUI attachment with preview and download guidance.
"""

import asyncio
import base64
import html
import io
import json
import random
import re
import uuid
from typing import Any, Awaitable, Callable, Literal

import aiohttp
from open_webui.models.files import FileForm, Files
from open_webui.storage.provider import Storage
from pydantic import BaseModel, Field


ELEVENLABS_API = "https://api.elevenlabs.io/v1"
QUALITY_MODEL = "eleven_multilingual_v2"
FAST_MODEL = "eleven_flash_v2_5"
MODEL_LIMITS = {QUALITY_MODEL: 10_000, FAST_MODEL: 40_000, "eleven_v3": 5_000}
EventEmitter = Callable[[dict[str, Any]], Awaitable[Any]]
EventCall = Callable[[dict[str, Any]], Awaitable[Any]]


def clean_speech(content: Any) -> str:
    """Reduce an assistant response to readable narration text."""
    if isinstance(content, list):
        content = "\n".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") in {"text", "input_text"}
        )
    if not isinstance(content, str):
        return ""
    text = re.sub(r"```[\s\S]*?```", "", content)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<https?://[^>]+>", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"(?m)^\s{0,3}(?:#{1,6}|>|[-+*]|\d+[.)])\s+", "", text)
    text = re.sub(r"(?<!\w)[*_~`]+|[*_~`]+(?!\w)", "", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_voices(lines: str) -> tuple[dict[str, str], dict[str, str]]:
    voices: dict[str, str] = {}
    descriptions: dict[str, str] = {}
    for line in lines.splitlines():
        fields = line.split(":", 2)
        if len(fields) < 2 or not fields[0].strip() or not fields[1].strip():
            continue
        name = fields[0].strip()
        voices[name] = fields[1].strip()
        if len(fields) == 3 and fields[2].strip():
            descriptions[name] = fields[2].strip()
    return voices, descriptions


def find_voice(value: str, voices: dict[str, str]) -> tuple[str, str] | None:
    wanted = value.strip().casefold()
    return next(
        ((name, voice_id) for name, voice_id in voices.items() if name.casefold() == wanted),
        None,
    )


def file_url(file_id: str, attachment: bool = False) -> str:
    suffix = "?attachment=true" if attachment else ""
    return f"/api/v1/files/{file_id}/content{suffix}"


def attachment(file_id: str, filename: str, size: int) -> dict[str, Any]:
    """Open WebUI File Object for the persisted short `files` event."""
    return {
        "type": "file",
        "id": file_id,
        "name": filename,
        "url": file_url(file_id, attachment=True),
        "content_type": "audio/mpeg",
        "size": size,
    }


def completion(body: dict[str, Any], voice_name: str, file_id: str) -> dict[str, Any]:
    """Return the supported Action message-update shape without losing the reply."""
    message_id = body.get("id")
    if not message_id:
        return {}
    source = next(
        (
            message.get("content", "")
            for message in reversed(body.get("messages", []))
            if message.get("role") == "assistant"
        ),
        "",
    )
    link = f"[Download MP3]({file_url(file_id, attachment=True)})"
    if link in source:
        content = source
    else:
        notice = (
            f"🎧 **Audio ready, {voice_name}.** {link}  \\n"
            "You can also open the attached MP3 to preview it or use its download control."
        )
        content = f"{source.rstrip()}\n\n{notice}" if source else notice
    return {"messages": [{"id": message_id, "content": content}]}


def download_panel_script(audio: bytes, filename: str, voice_name: str) -> str:
    """Build a visible main-page download control via Open WebUI's execute event."""
    encoded = base64.b64encode(audio).decode("ascii")
    safe_voice = json.dumps(voice_name)
    return f"""(() => {{
      const existing = document.getElementById('wl-tts-download-panel');
      if (existing) existing.remove();
      const data = {json.dumps(encoded)};
      const filename = {json.dumps(filename)};
      const panel = document.createElement('div'); panel.id = 'wl-tts-download-panel';
      panel.style.cssText = 'position:fixed;right:20px;bottom:20px;z-index:2147483647;background:#171717;color:#fff;border:1px solid #555;border-radius:12px;padding:14px 16px;box-shadow:0 8px 30px #0008;font:14px system-ui,sans-serif;display:flex;align-items:center;gap:12px';
      const text = document.createElement('span'); text.textContent = 'Audio ready (' + {safe_voice} + ')';
      const button = document.createElement('button'); button.textContent = 'Download MP3';
      button.style.cssText = 'border:0;border-radius:8px;padding:8px 12px;background:#2563eb;color:#fff;font-weight:700;cursor:pointer';
      button.onclick = () => {{ const binary = atob(data); const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
        const url = URL.createObjectURL(new Blob([bytes], {{type:'audio/mpeg'}}));
        const link = document.createElement('a'); link.href = url; link.download = filename;
        document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
      }};
      const close = document.createElement('button'); close.textContent = '×'; close.setAttribute('aria-label', 'Close');
      close.style.cssText = 'border:0;background:transparent;color:#aaa;font-size:20px;cursor:pointer'; close.onclick = () => panel.remove();
      panel.append(text, button, close); document.body.appendChild(panel);
    }})()"""


class Action:
    class Valves(BaseModel):
        ELEVENLABS_API_KEY: str = Field(default="", description="ElevenLabs API key.")
        PLAYBACK_MODE: Literal["quality", "fast"] = Field(default="quality")
        DEFAULT_VOICE: str = Field(default="Donovan")
        CUSTOM_VOICES: str = Field(
            default=(
                "Donovan:DMyrgzQFny3JI1Y1paM5:Articulate, strong, and deep\n"
                "Jessica:g6xIsTj2HwM6VR4iXFCw:Friendly and conversational\n"
                "Mark:1SM7GgM6IMuvQlz2BwM3:Conversational\n"
                "Archer:Fahco4VZzobUeiPqni1S:Conversational\n"
                "Brittney:kPzsL2i3teMYv0FxEYQ6:Fun, youthful, and informal"
            ),
            description="One voice per line: Name:VoiceID:optional description.",
        )
        MAX_CHARACTERS: int = Field(default=9_000, ge=100, le=40_000)
        REQUEST_TIMEOUT_SECONDS: int = Field(default=90, ge=10, le=300)
        RETRY_ATTEMPTS: int = Field(default=2, ge=0, le=4)

    def __init__(self):
        self.valves = self.Valves()

    @property
    def model_id(self) -> str:
        return FAST_MODEL if self.valves.PLAYBACK_MODE == "fast" else QUALITY_MODEL

    @staticmethod
    def status(description: str, done: bool = False) -> dict[str, Any]:
        return {"type": "status", "data": {"description": description, "done": done}}

    async def choose_voice(
        self, voices: dict[str, str], descriptions: dict[str, str], event_call: EventCall | None
    ) -> tuple[str, str]:
        default = find_voice(self.valves.DEFAULT_VOICE, voices) or next(iter(voices.items()))
        if event_call is None:
            return default
        options = "\n".join(
            f"• **{name}**" + (f" — {descriptions[name]}" if name in descriptions else "")
            for name in voices
        )
        response = await event_call(
            {
                "type": "input",
                "data": {
                    "title": "Select ElevenLabs voice",
                    "message": f"Choose a listed voice name:\n\n{options}",
                    "placeholder": "Voice name",
                    "value": default[0],
                },
            }
        )
        selected = response if isinstance(response, str) else (response or {}).get("message", "")
        resolved = find_voice(str(selected), voices)
        if resolved is None:
            raise ValueError("Voice selection was cancelled or did not match a curated voice.")
        return resolved

    @staticmethod
    async def response_error(response: aiohttp.ClientResponse) -> str:
        try:
            payload = await response.json(content_type=None)
            return str(payload.get("detail") or payload.get("message") or payload)
        except Exception:
            return (await response.text())[:500]

    async def synthesize(self, voice_id: str, text: str) -> bytes:
        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.5},
        }
        timeout = aiohttp.ClientTimeout(total=self.valves.REQUEST_TIMEOUT_SECONDS)
        headers = {"xi-api-key": self.valves.ELEVENLABS_API_KEY, "Content-Type": "application/json"}
        for attempt in range(self.valves.RETRY_ATTEMPTS + 1):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        f"{ELEVENLABS_API}/text-to-speech/{voice_id}",
                        params={"output_format": "mp3_44100_128"}, json=payload, headers=headers,
                    ) as response:
                        if response.status < 400:
                            return await response.read()
                        detail = await self.response_error(response)
                        retryable = response.status == 429 or response.status >= 500
                        retry_after = response.headers.get("Retry-After")
                if not retryable or attempt == self.valves.RETRY_ATTEMPTS:
                    raise ValueError(f"ElevenLabs could not generate speech (HTTP {response.status}): {detail}")
            except aiohttp.ClientError as exc:
                if attempt == self.valves.RETRY_ATTEMPTS:
                    raise ValueError(f"ElevenLabs connection failed: {exc}") from exc
                retry_after = None
            try:
                delay = min(30.0, max(0.0, float(retry_after))) if retry_after else random.uniform(0, min(8.0, 0.5 * 2**attempt))
            except ValueError:
                delay = random.uniform(0, min(8.0, 0.5 * 2**attempt))
            await asyncio.sleep(delay)
        raise ValueError("ElevenLabs could not generate speech.")

    @staticmethod
    async def save_audio(filename: str, audio: bytes, user: dict[str, Any]) -> str | None:
        """Store an audio file using Open WebUI's owned-file API."""
        try:
            file_id = str(uuid.uuid4())
            contents, path = await asyncio.to_thread(
                Storage.upload_file, io.BytesIO(audio), f"{file_id}_{filename}", {}
            )
            record = await Files.insert_new_file(
                user["id"],
                FileForm(
                    **{
                        "id": file_id,
                        "filename": filename,
                        "path": path,
                        "data": {
                            "content": (
                                "This is an MP3 audio file generated by ElevenLabs. "
                                "Choose Preview to listen, or use Download to save the file."
                            )
                        },
                        "meta": {
                            "name": filename,
                            "content_type": "audio/mpeg",
                            "size": len(contents),
                            "data": {"title": "Generated ElevenLabs audio"},
                        },
                    }
                ),
            )
            return record.id
        except Exception:
            return None

    async def action(
        self,
        body: dict[str, Any],
        __user__: dict[str, Any] | None = None,
        __event_emitter__: EventEmitter | None = None,
        __event_call__: EventCall | None = None,
    ) -> dict[str, Any]:
        try:
            user = __user__ or {}
            if not self.valves.ELEVENLABS_API_KEY.strip():
                raise ValueError("ElevenLabs API key is not configured in this action.")
            if not user.get("id"):
                raise ValueError("Sign in to generate a private audio file.")
            source = next(
                (m.get("content") for m in reversed(body.get("messages", [])) if m.get("role") == "assistant"),
                None,
            )
            text = clean_speech(source)
            if not text:
                raise ValueError("The latest assistant reply has no narratable text.")
            limit = min(self.valves.MAX_CHARACTERS, MODEL_LIMITS.get(self.model_id, self.valves.MAX_CHARACTERS))
            if len(text) > limit:
                raise ValueError(f"This reply is {len(text):,} characters; this voice mode supports up to {limit:,}.")
            if __event_emitter__:
                await __event_emitter__(self.status("Preparing speech"))
            voices, descriptions = parse_voices(self.valves.CUSTOM_VOICES)
            if not voices:
                raise ValueError("No curated voices are configured.")
            voice_name, voice_id = await self.choose_voice(voices, descriptions, __event_call__)
            if __event_emitter__:
                await __event_emitter__(self.status(f"Generating speech with {voice_name}"))
            audio = await self.synthesize(voice_id, text)
            if not audio:
                raise ValueError("ElevenLabs returned an empty audio file.")
            filename = f"tts_{uuid.uuid4()}.mp3"
            file_id = await self.save_audio(filename, audio, user)
            if not file_id:
                raise ValueError("Speech was generated but could not be saved as an Open WebUI file.")
            if __event_emitter__:
                # The short event name is required for server-side persistence.
                await __event_emitter__({"type": "files", "data": {"files": [attachment(file_id, filename, len(audio))]}})
                await __event_emitter__({"type": "execute", "data": {"code": download_panel_script(audio, filename, voice_name)}})
                await __event_emitter__(self.status("Audio generated", done=True))
            return completion(body, voice_name, file_id)
        except ValueError as exc:
            message = str(exc)
        except Exception:
            message = "Audio generation failed unexpectedly. Please try again."
        if __event_emitter__:
            await __event_emitter__(self.status("Audio generation failed", done=True))
            await __event_emitter__({"type": "notification", "data": {"type": "error", "content": message}})
        message_id = body.get("id")
        return {"messages": [{"id": message_id, "content": message}]} if message_id else {}
