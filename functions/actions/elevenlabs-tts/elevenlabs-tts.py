"""
title: ElevenLabs TTS Action
author: justinh-rahb
author_url: https://github.com/justinh-rahb
funding_url: https://github.com/open-webui
version: 0.2.0
license: MIT
icon_url: data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzIiIGhlaWdodD0iMzIiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHJlY3QgeD0iOCIgeT0iNiIgd2lkdGg9IjYiIGhlaWdodD0iMjAiIGZpbGw9IiM0QzRDNEMiLz48cmVjdCB4PSIxOCIgeT0iNiIgd2lkdGg9IjYiIGhlaWdodD0iMjAiIGZpbGw9IiM0QzRDNEMiLz48L3N2Zz4=
required_open_webui_version: 0.3.10
requirements: aiohttp, pydantic
description: Convert assistant messages to speech using ElevenLabs TTS with configurable voice selection and default voice support
"""

import aiohttp
import uuid
import os
import io
import base64
from pydantic import BaseModel, Field
from typing import Callable, Any
from open_webui.config import UPLOAD_DIR
from open_webui.models.files import Files, FileForm
from open_webui.storage.provider import Storage

DEBUG = True


class Action:
    class Valves(BaseModel):
        ELEVENLABS_API_KEY: str = Field(
            default=None, description="Your ElevenLabs API key."
        )
        ELEVENLABS_MODEL_ID: str = Field(
            default="eleven_multilingual_v2",
            description="ID of the ElevenLabs TTS model to use.",
        )
        DEFAULT_VOICE: str = Field(
            default="Donovan",
            description="Default voice to use for text-to-speech generation. Change this to your preferred voice for quick one-click TTS.",
        )
        CUSTOM_VOICES: str = Field(
            default="Donovan:DMyrgzQFny3JI1Y1paM5:Articulate, Strong and Deep\nJessica:g6xIsTj2HwM6VR4iXFCw:Friendly and Conversational\nMark:1SM7GgM6IMuvQlz2BwM3:ConvoAI\nArcher:Fahco4VZzobUeiPqni1S:Conversational\nBrittney:kPzsL2i3teMYv0FxEYQ6:Fun, Youthful and Informal",
            description="Custom voices in format: VoiceName:VoiceID:Description (one per line). Only these voices will be shown.",
        )
        AUDIO_FORMAT: str = Field(
            default="mp3",
            description="Audio format for generated files. Options: mp3, wav, pcm_16000, ulaw_8000",
            json_schema_extra={"enum": ["mp3", "wav", "pcm_16000", "ulaw_8000"]},
        )

    def __init__(self):
        self.valves = self.Valves()
        self.voice_id_cache = {}

    def status_object(
        self,
        description: str = "Unknown State",
        status: str = "in_progress",
        done: bool = False,
    ) -> dict[str, Any]:
        return {
            "type": "status",
            "data": {
                "description": description,
                "done": done,
            },
        }

    async def fetch_available_voices(self) -> tuple[str, dict[str, str]]:
        if DEBUG:
            print("Debug: Fetching available voices")

        base_url = "https://api.elevenlabs.io/v1"
        headers = {
            "xi-api-key": self.valves.ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
        }

        voices_url = f"{base_url}/voices"
        try:
            # First, parse custom voices from Valves
            custom_voice_map = {}
            custom_voice_descriptions = {}
            if self.valves.CUSTOM_VOICES:
                for line in self.valves.CUSTOM_VOICES.strip().split("\n"):
                    if ":" in line:
                        parts = line.split(":", 2)  # Split into max 3 parts
                        if len(parts) >= 2:
                            voice_name = parts[0].strip()
                            voice_id = parts[1].strip()
                            description = parts[2].strip() if len(parts) > 2 else ""
                            custom_voice_map[voice_name] = voice_id
                            if description:
                                custom_voice_descriptions[voice_name] = description
            
            if DEBUG:
                print(f"Debug: Parsed {len(custom_voice_map)} custom voices")
                print(f"Debug: Custom voices: {list(custom_voice_map.keys())}")
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.get(voices_url, headers=headers) as response:
                    response.raise_for_status()
                    voices_data = await response.json()

                    # Build voice options dictionary - use ONLY custom voices if configured
                    voice_options = {}
                    if custom_voice_map:
                        voice_options = custom_voice_map.copy()
                    else:
                        # Fallback to API voices if no custom voices
                        for voice in voices_data.get("voices", []):
                            voice_name = voice["name"]
                            voice_id = voice["voice_id"]
                            base_name = voice_name.split(" - ")[0].strip()
                            voice_options[base_name] = voice_id
                    
                    if DEBUG:
                        print(f"Debug: Using {len(voice_options)} custom voices")
                        print(f"Debug: Voices: {list(voice_options.keys())}")
                    
                    # Build display message with custom voice descriptions
                    display_message = "**Available Voices** (copy-paste the name):\n\n"
                    
                    for voice_name in voice_options.keys():
                        description = custom_voice_descriptions.get(voice_name, "")
                        if description:
                            display_message += f"• **{voice_name}** - {description}\n"
                        else:
                            display_message += f"• **{voice_name}**\n"

                    return display_message, voice_options

        except aiohttp.ClientResponseError as e:
            if DEBUG:
                print(f"Debug: HTTP error fetching voices: {e.status} - {e.message}")
            return f"Sorry, couldn't fetch available voices at the moment (HTTP {e.status}).", {}
        except aiohttp.ClientError as e:
            if DEBUG:
                print(f"Debug: Network error fetching voices: {str(e)}")
            return "Sorry, couldn't fetch available voices at the moment (network error).", {}
        except Exception as e:
            if DEBUG:
                print(f"Debug: Unexpected error fetching voices: {str(e)}")
            return "Sorry, couldn't fetch available voices at the moment.", {}

    async def action(
        self,
        body: dict,
        __user__: dict = {},
        __event_emitter__: Callable[[dict[str, Any]], Any] = None,
        __event_call__: Callable[[dict[str, Any]], Any] = None,
    ) -> dict[str, Any]:
        if DEBUG:
            print(f"Debug: ElevenLabs TTS action invoked")

        try:
            if __event_emitter__:
                await __event_emitter__(
                    self.status_object("Initializing ElevenLabs Text-to-Speech")
                )

            if not self.valves.ELEVENLABS_API_KEY or not self.valves.ELEVENLABS_API_KEY.strip():
                raise ValueError("ElevenLabs API key is not configured. Please set it in the function settings.")

            if "id" not in __user__:
                raise ValueError("User not authenticated")

            display_message, self.voice_id_cache = await self.fetch_available_voices()

            if not self.voice_id_cache:
                raise ValueError("No available voices to select")

            if not __event_call__:
                raise ValueError("Action requires user interaction but event_call is not available")

            # Use default voice from Valves, or fallback to first available voice
            default_voice = self.valves.DEFAULT_VOICE
            
            # Try case-insensitive match for default voice
            if default_voice not in self.voice_id_cache:
                voice_names_lower = {name.lower(): name for name in self.voice_id_cache.keys()}
                if default_voice.lower() in voice_names_lower:
                    default_voice = voice_names_lower[default_voice.lower()]
                else:
                    # Fallback to first available voice if default not found
                    default_voice = list(self.voice_id_cache.keys())[0]
                    if DEBUG:
                        print(f"Debug: Default voice '{self.valves.DEFAULT_VOICE}' not found. Using '{default_voice}' instead.")
            
            response = await __event_call__(
                {
                    "type": "input",
                    "data": {
                        "title": "Select Voice for Text-to-Speech",
                        "message": display_message,
                        "placeholder": "Copy-paste a voice name from above",
                        "value": default_voice,
                    },
                }
            )

            if DEBUG:
                print(f"Debug: Voice selection response: {response}")

            # Handle user cancellation or empty response
            if not response or (isinstance(response, str) and not response.strip()):
                raise ValueError("Voice selection was cancelled or empty")

            # For select input, response should be the selected option (string)
            if isinstance(response, str):
                selected_voice_name = response.strip()
            elif isinstance(response, dict):
                selected_voice_name = response.get("message", "").strip()
            else:
                raise ValueError(f"Unexpected response type: {type(response)}")

            # Validate the selected voice exists in our cache (case-insensitive)
            selected_voice_id = None
            
            # First try exact match
            if selected_voice_name in self.voice_id_cache:
                selected_voice_id = self.voice_id_cache[selected_voice_name]
            else:
                # Try case-insensitive match
                voice_name_lower = selected_voice_name.lower()
                for voice_name, voice_id in self.voice_id_cache.items():
                    if voice_name.lower() == voice_name_lower:
                        selected_voice_id = voice_id
                        selected_voice_name = voice_name  # Use the correct casing
                        break

            if DEBUG:
                print(f"Debug: Selected voice: {selected_voice_name} ({selected_voice_id})")
                print(f"Debug: Available voices: {list(self.voice_id_cache.keys())[:10]}")

            if not selected_voice_id:
                available_voices = ", ".join(list(self.voice_id_cache.keys())[:10])
                raise ValueError(
                    f"Invalid voice selection: '{selected_voice_name}' not found. "
                    f"Available voices include: {available_voices}"
                )

            messages = body.get("messages", [])
            assistant_message = next(
                (
                    message.get("content")
                    for message in reversed(messages)
                    if message.get("role") == "assistant"
                ),
                None,
            )

            if not assistant_message or not assistant_message.strip():
                raise ValueError("No assistant message content found to convert to speech")

            if __event_emitter__:
                await __event_emitter__(self.status_object("Generating speech"))

            base_url = "https://api.elevenlabs.io/v1"
            headers = {
                "xi-api-key": self.valves.ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
            }

            tts_url = f"{base_url}/text-to-speech/{selected_voice_id}"
            payload = {
                "text": assistant_message,
                "model_id": self.valves.ELEVENLABS_MODEL_ID,
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.5},
                "output_format": self.valves.AUDIO_FORMAT,
            }

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                async with session.post(tts_url, json=payload, headers=headers) as response:
                    response.raise_for_status()

                    if response.status == 200:
                        audio_data = await response.read()
                        # Use configured audio format for file extension
                        audio_ext = self.valves.AUDIO_FORMAT
                        file_name = f"tts_{uuid.uuid4()}.{audio_ext}"
                        
                        # Determine MIME type based on format
                        mime_type_map = {
                            "mp3": "audio/mpeg",
                            "wav": "audio/wav",
                            "pcm_16000": "audio/pcm",
                            "ulaw_8000": "audio/ulaw",
                        }
                        mime_type = mime_type_map.get(audio_ext, "audio/mpeg")

                        file_id = self._create_file(
                            file_name, "Generated Audio", audio_data, mime_type, __user__
                        )
                        if file_id:
                            file_url = self._get_file_url(file_id)
                            if __event_emitter__:
                                await __event_emitter__(
                                    self.status_object(
                                        "Generated successfully", done=True
                                    )
                                )
                            if file_url:
                                await __event_emitter__(
                                    {
                                        "type": "message",
                                        "data": {
                                            "content": f"""
**Audio Generated Successfully!**

[Download Audio]({file_url})

*Note: Downloading not supported on iOS.*
"""
                                        },
                                    }
                                )
                                return {"content": f"Audio generated successfully using ElevenLabs voice **{selected_voice_name}**. Download: {file_url}"}
                        else:
                            raise ValueError("Error saving audio file")
                    else:
                        response_text = await response.text()
                        raise ValueError(f"Unexpected API response: {response.status} - {response_text}")

        except ValueError as e:
            # Handle user input/validation errors
            error_msg = f"Validation Error: {str(e)}"
            if DEBUG:
                print(f"Debug: {error_msg}")
            if __event_emitter__:
                await __event_emitter__(
                    self.status_object("Validation failed", done=True)
                )
                await __event_emitter__({
                    "type": "notification",
                    "data": {
                        "type": "error",
                        "content": error_msg
                    }
                })
            return {"content": error_msg}

        except Exception as e:
            # Handle unexpected errors
            error_msg = f"Unexpected error: {str(e)}"
            if DEBUG:
                print(f"Debug: {error_msg}")
            if __event_emitter__:
                await __event_emitter__(
                    self.status_object("An error occurred", done=True)
                )
                await __event_emitter__({
                    "type": "notification",
                    "data": {
                        "type": "error",
                        "content": error_msg
                    }
                })
            return {"content": error_msg}

    def _create_file(
        self,
        file_name: str,
        title: str,
        content: str | bytes,
        content_type: str,
        __user__: dict = {},
    ) -> str:
        if DEBUG:
            print(f"Debug: Creating file: {file_name}")

        if "id" not in __user__:
            if DEBUG:
                print("Debug: User ID is not available")
            return None

        try:
            file_id = str(uuid.uuid4())
            filename_with_id = f"{file_id}_{file_name}"

            if isinstance(content, str):
                file_obj = io.StringIO(content)
            else:
                file_obj = io.BytesIO(content)

            contents, file_path = Storage.upload_file(file_obj, filename_with_id, {})

            file_item = Files.insert_new_file(
                __user__["id"],
                FileForm(
                    **{
                        "id": file_id,
                        "filename": file_name,
                        "path": file_path,
                        "meta": {
                            "name": file_name,
                            "content_type": content_type,
                            "size": len(contents),
                            "data": {"title": title},
                        },
                    }
                ),
            )

            if DEBUG:
                print(f"Debug: File saved. Path: {file_path}")
            return file_item.id
        except Exception as e:
            if DEBUG:
                print(f"Debug: Error saving file: {e}")
            return None

    def _get_file_url(self, file_id: str) -> str:
        return f"/api/v1/files/{file_id}/content"
