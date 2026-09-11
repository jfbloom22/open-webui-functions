"""
title: ElevenLabs TTS, Embedded Player
author: Workplace Labs
version: 1.1.0
license: MIT
requirements: aiohttp, pydantic
description: Generate speech in a self-contained, persistent player with an explicit MP3 download button.
"""

"""A function-only alternative to Open WebUI's native file attachment UI.

The audio is embedded as base64 inside Open WebUI's documented ``embeds`` event.
That makes the player and download control independent of the browser's authenticated
``/api/v1/files/...`` navigation behaviour. The trade-off is intentionally bounded by
MAX_EMBED_AUDIO_BYTES: embed payloads live in chat history, so this is for short-form
narration rather than long podcasts.
"""

import asyncio
import base64
import html
import json
import random
import re
import uuid
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


def embed_html(audio: bytes, filename: str, voice_name: str) -> str:
    """Build a self-contained player that does not need Open WebUI auth in its iframe.

    An object URL is created inside the sandboxed iframe from the base64 payload. This
    avoids an iframe request to Open WebUI's protected Files endpoint, which cannot
    access the parent page's localStorage token by default.
    """
    encoded = base64.b64encode(audio).decode("ascii")
    safe_filename = html.escape(filename, quote=True)
    safe_voice = html.escape(voice_name)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {{ color-scheme: light dark; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; padding: 12px; font-family: ui-sans-serif, system-ui, sans-serif; }}
    .card {{ border: 1px solid color-mix(in srgb, currentColor 18%, transparent); border-radius: 12px; padding: 14px; }}
    .title {{ font-weight: 700; margin: 0 0 3px; }}
    .meta {{ margin: 0 0 12px; opacity: .72; font-size: .88rem; }}
    audio {{ display: block; width: 100%; margin-bottom: 12px; }}
    .download {{ display: inline-block; padding: 8px 12px; border-radius: 8px; background: #2563eb; color: white; font-weight: 650; text-decoration: none; }}
    .hint {{ margin: 9px 0 0; opacity: .68; font-size: .78rem; }}
  </style>
</head>
<body>
  <section class="card" aria-label="Generated ElevenLabs audio">
    <p class="title">Audio ready</p>
    <p class="meta">Voice: {safe_voice} · MP3</p>
    <audio id="player" controls preload="metadata">Your browser does not support audio playback.</audio>
    <a id="download" class="download" download="{safe_filename}" href="#">Download MP3</a>
    <p class="hint">Preview above, then use Download MP3 to save a copy.</p>
  </section>
  <script>
    (() => {{
      const base64Audio = '{encoded}';
      const binary = atob(base64Audio);
      const bytes = new Uint8Array(binary.length);
      for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
      const url = URL.createObjectURL(new Blob([bytes], {{ type: 'audio/mpeg' }}));
      document.getElementById('player').src = url;
      document.getElementById('download').href = url;
      const reportHeight = () => parent.postMessage({{ type: 'iframe:height', height: document.documentElement.scrollHeight }}, '*');
      window.addEventListener('load', reportHeight);
      new ResizeObserver(reportHeight).observe(document.body);
      window.addEventListener('beforeunload', () => URL.revokeObjectURL(url));
    }})();
  </script>
</body>
</html>"""


def download_panel_script(audio: bytes, filename: str, voice_name: str) -> str:
    """Build the same download control in the trusted main page, not the iframe."""
    encoded = base64.b64encode(audio).decode("ascii")
    return f"""(() => {{
      const existing = document.getElementById('wl-tts-download-panel'); if (existing) existing.remove();
      const data = {json.dumps(encoded)}; const filename = {json.dumps(filename)};
      const panel = document.createElement('div'); panel.id = 'wl-tts-download-panel';
      panel.style.cssText = 'position:fixed;right:20px;bottom:20px;z-index:2147483647;background:#171717;color:#fff;border:1px solid #555;border-radius:12px;padding:14px 16px;box-shadow:0 8px 30px #0008;font:14px system-ui,sans-serif;display:flex;align-items:center;gap:12px';
      const text = document.createElement('span'); text.textContent = 'Audio ready (' + {json.dumps(voice_name)} + ')';
      const button = document.createElement('button'); button.textContent = 'Download MP3';
      button.style.cssText = 'border:0;border-radius:8px;padding:8px 12px;background:#2563eb;color:#fff;font-weight:700;cursor:pointer';
      button.onclick = () => {{ const binary = atob(data); const bytes = new Uint8Array(binary.length); for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
        const url = URL.createObjectURL(new Blob([bytes], {{type:'audio/mpeg'}})); const link = document.createElement('a'); link.href = url; link.download = filename;
        document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000); }};
      const close = document.createElement('button'); close.textContent = '×'; close.setAttribute('aria-label', 'Close'); close.style.cssText = 'border:0;background:transparent;color:#aaa;font-size:20px;cursor:pointer'; close.onclick = () => panel.remove();
      panel.append(text, button, close); document.body.appendChild(panel);
    }})()"""


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
    notice = f"Audio ready with **{voice_name}**. Use the player and **Download MP3** button above."
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
        MAX_CHARACTERS: int = Field(default=2200, ge=100, le=10000)
        MAX_EMBED_AUDIO_BYTES: int = Field(
            default=2_500_000,
            ge=100_000,
            le=10_000_000,
            description="Largest MP3 stored directly in chat history. Keep this small for responsive chats.",
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

    async def generate_audio(self, voice_id: str, text: str) -> bytes:
        headers = {"xi-api-key": self.valves.ELEVENLABS_API_KEY, "Content-Type": "application/json"}
        payload = {
            "text": text,
            "model_id": self.selected_model(),
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.5},
        }
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
            limit = min(self.valves.MAX_CHARACTERS, model_limit)
            if len(text) > limit:
                raise ValueError(f"This reply is {len(text):,} characters after cleanup; this player supports {limit:,}.")
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
            if __event_emitter__:
                await __event_emitter__(self.status(f"Generating speech with {voice_name}"))
            audio = await self.generate_audio(voice_id, text)
            if len(audio) > self.valves.MAX_EMBED_AUDIO_BYTES:
                raise ValueError(
                    f"This MP3 is {len(audio) / 1_000_000:.1f} MB, above this variant's {self.valves.MAX_EMBED_AUDIO_BYTES / 1_000_000:.1f} MB embedded-player limit. Try a shorter response or another audio action."
                )
            filename = f"tts_{uuid.uuid4()}.mp3"
            if __event_emitter__:
                await __event_emitter__(
                    {"type": "embeds", "data": {"embeds": [embed_html(audio, filename, voice_name)], "replace": True}}
                )
                await __event_emitter__({"type": "execute", "data": {"code": download_panel_script(audio, filename, voice_name)}})
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
