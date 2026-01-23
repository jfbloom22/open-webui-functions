"""
title: ElevenLabs Text-to-Speech Tool
author: justinh-rahb
author_url: https://github.com/justinh-rahb
funding_url: https://github.com/open-webui
version: 0.2.3
license: MIT
"""

import requests
import uuid
import os
from pydantic import BaseModel, Field
from typing import Callable, Union, Any
from config import UPLOAD_DIR
from apps.webui.models.files import Files

DEBUG = False


class Tools:
    class Valves(BaseModel):
        ELEVENLABS_API_KEY: str = Field(
            default=None, description="Your ElevenLabs API key."
        )
        ELEVENLABS_MODEL_ID: str = Field(
            default="eleven_multilingual_v2",
            description="ID of the ElevenLabs TTS model to use.",
        )

    def __init__(self):
        self.valves = self.Valves()
        self.voice_id_cache = {}

    def fetch_available_voices(self) -> str:
        """
        Fetches the list of available voices from the ElevenLabs API.

        :return: A formatted string containing the names and descriptions of available voices.
        """
        if DEBUG:
            print("Debug: Fetching available voices")

        base_url = "https://api.elevenlabs.io/v1"
        headers = {
            "xi-api-key": self.valves.ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
        }

        voices_url = f"{base_url}/voices"
        try:
            response = requests.get(voices_url, headers=headers)
            response.raise_for_status()
            voices_data = response.json()

            message = "Here are the available voices from ElevenLabs:\n\n"
            for voice in voices_data["voices"]:
                message += f"- {voice['name']}: {voice.get('description', 'No description available.')}\n"
                self.voice_id_cache[voice["name"].lower()] = voice["voice_id"]

            if DEBUG:
                print(f"Debug: Found {len(voices_data['voices'])} voices")

            return message
        except requests.RequestException as e:
            if DEBUG:
                print(f"Debug: Error fetching voices: {str(e)}")
            return "Sorry, I couldn't fetch the list of available voices at the moment."

    def get_voice_list(self) -> str:
        """
        Retrieves and returns a list of available voices as a formatted string.

        :return: A formatted string containing the list of voices.
        """
        voices_message = self.fetch_available_voices()
        return voices_message

    async def elevenlabs_text_to_speech(
        self,
        text: str,
        voice_name: str = "rachel",
        __user__: dict = {},
        __event_emitter__: Callable[[dict], Any] = None,
    ) -> str:
        """
        Converts text to speech using the ElevenLabs API or lists available voices.

        :param text: The text to convert to speech or "list voices" to retrieve available voices.
        :param voice_name: The name of the voice to use for speech generation. Defaults to "rachel".
        :param __user__: A dictionary containing user information.
        :param __event_emitter__: An optional callback function to emit status events throughout the process.
        :return: A message indicating the result of the operation (success or error).
        """

        if DEBUG:
            print(
                f"Debug: Starting TTS for voice '{voice_name}' with text '{text[:20]}...'"
            )

        def status_object(
            description="Unknown State", status="in_progress", done=False
        ):
            """
            Helper function to create a status object.

            :param description: A short description of the current status.
            :param status: Status type (e.g., 'in_progress', 'error', 'complete').
            :param done: Boolean indicating whether the operation is done.
            :return: A dictionary representing the status object.
            """
            return {
                "type": "status",
                "data": {
                    "status": status,
                    "description": description,
                    "done": done,
                },
            }

        if __event_emitter__:
            await __event_emitter__(
                status_object("Initializing ElevenLabs Text-to-Speech")
            )

        if not self.valves.ELEVENLABS_API_KEY:
            if __event_emitter__:
                await __event_emitter__(
                    status_object("Error: API key not set", status="error", done=True)
                )
            return "ElevenLabs API key is not set. Please set it in your environment variables."

        if "id" not in __user__:
            if __event_emitter__:
                await __event_emitter__(
                    status_object(
                        "Error: User not authenticated", status="error", done=True
                    )
                )
            return "Error: User ID is not available. Please ensure you're logged in."

        if text.lower().strip() in [
            "list voices",
            "show voices",
            "available voices",
            "what voices are available",
        ]:
            voices = self.get_voice_list()
            if __event_emitter__:
                await __event_emitter__(
                    status_object(
                        "Available voices fetched", status="complete", done=True
                    )
                )
            return voices

        voice_id = self.voice_id_cache.get(voice_name.lower())
        if not voice_id:
            voices_message = self.fetch_available_voices()
            if voices_message.startswith("Sorry, I couldn't fetch"):
                if __event_emitter__:
                    await __event_emitter__(
                        status_object(
                            "Error: Could not fetch voices", status="error", done=True
                        )
                    )
                return voices_message

            voice_id = self.voice_id_cache.get(voice_name.lower())
            if not voice_id:
                if __event_emitter__:
                    await __event_emitter__(
                        status_object(
                            f"Error: Voice '{voice_name}' not found",
                            status="error",
                            done=True,
                        )
                    )
                return f"Error: Voice '{voice_name}' not found. Use 'list voices' to see available options."

        if __event_emitter__:
            await __event_emitter__(status_object("Generating speech"))

        base_url = "https://api.elevenlabs.io/v1"
        headers = {
            "xi-api-key": self.valves.ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
        }

        tts_url = f"{base_url}/text-to-speech/{voice_id}"
        payload = {
            "text": text,
            "model_id": self.valves.ELEVENLABS_MODEL_ID,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.5},
        }

        try:
            response = requests.post(tts_url, json=payload, headers=headers)
            response.raise_for_status()

            if response.status_code == 200:
                audio_data = response.content
                file_name = f"tts_{uuid.uuid4()}.mp3"

                file_id = self._create_file(
                    file_name, "Generated Audio", audio_data, "audio/mpeg", __user__
                )
                if file_id:
                    file_url = self._get_file_url(file_id)
                    if __event_emitter__:
                        await __event_emitter__(
                            status_object(
                                "Generated successfully",
                                status="complete",
                                done=True,
                            )
                        )
                    if file_url:
                        if __event_emitter__:
                            await __event_emitter__(
                                {
                                    "type": "message",
                                    "data": {
                                        "content": f"\n[click to listen]({file_url})\n"
                                    },
                                }
                            )
                    return f"Audio generated successfully using ElevenLabs voice **{voice_name}**. Right click and **Save Link As** to download [the audio file]({file_url})."
                else:
                    if __event_emitter__:
                        await __event_emitter__(
                            status_object(
                                "Error saving audio file", status="error", done=True
                            )
                        )
                    return "Error saving audio file."
            else:
                if __event_emitter__:
                    await __event_emitter__(
                        status_object(
                            f"Error: Unexpected API response", status="error", done=True
                        )
                    )
                return f"Error generating speech: {response.text}"

        except requests.RequestException as e:
            if __event_emitter__:
                await __event_emitter__(
                    status_object(
                        f"Error: API request failed", status="error", done=True
                    )
                )
            return f"Error generating speech: {str(e)}"

    def _create_file(
        self,
        file_name: str,
        title: str,
        content: Union[str, bytes],
        content_type: str,
        __user__: dict = {},
    ) -> str:
        """
        Creates and saves a file in the local upload directory and registers it with the Files API.

        :param file_name: The name of the file to save.
        :param title: The title of the file.
        :param content: The content of the file, either as a string or bytes.
        :param content_type: The MIME type of the file (e.g., "audio/mpeg").
        :param __user__: A dictionary containing user information.
        :return: The ID of the saved file, if successful; otherwise, None.
        """
        if DEBUG:
            print(f"Debug: Entering _create_file method")
            print(f"Debug: File name: {file_name}")
            print(f"Debug: Content type: {content_type}")
            print(f"Debug: User: {__user__}")

        if "id" not in __user__:
            if DEBUG:
                print("Debug: User ID is not available")
            return None

        base_path = os.path.join(UPLOAD_DIR)
        file_id = str(uuid.uuid4())

        file_path = os.path.join(base_path, f"{file_id}_{file_name}")
        mode = "w" if isinstance(content, str) else "wb"

        try:
            os.makedirs(base_path, exist_ok=True)
            with open(file_path, mode) as f:
                f.write(content)

            meta = {
                "source": file_path,
                "title": title,
                "content_type": content_type,
                "size": os.path.getsize(file_path),
                "path": file_path,
            }

            class FileForm(BaseModel):
                id: str
                filename: str
                meta: dict = {}

            formData = FileForm(id=file_id, filename=file_name, meta=meta)
            file = Files.insert_new_file(__user__["id"], formData)

            if DEBUG:
                print(f"Debug: File saved to local storage. File path: {file_path}")
                print(f"Debug: Meta information: {meta}")
            return file.id
        except Exception as e:
            if DEBUG:
                print(f"Debug: Error saving file: {e}")
            return None

    def _get_file_url(self, file_id: str) -> str:
        """
        Constructs and returns the URL to access the file content by its ID.

        :param file_id: The ID of the file.
        :return: The URL to access the file content.
        """
        return f"/api/v1/files/{file_id}/content"
