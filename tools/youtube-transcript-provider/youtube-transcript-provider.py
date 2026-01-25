"""
title: Youtube Transcript Provider
author: ekatiyar
author_url: https://github.com/ekatiyar
git_url: https://github.com/ekatiyar/open-webui-tools
description: A tool that returns the full youtube transcript of a passed in youtube url.
requirements: youtube-transcript-api, yt-dlp
version: 0.2.0
required_open_webui_version: 0.4.0
license: MIT
"""

import asyncio
import functools
import re
import tempfile
import os
from typing import Annotated, Any, Callable, Optional
from urllib.parse import urlparse, parse_qs

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptList
from pydantic import BaseModel, Field


def extract_video_id(url: str) -> Optional[str]:
    """
    Extracts the 11-character YouTube video ID from various URL formats.
    Handles standard, shortened, embed, and shorts URLs.
    """
    if not url:
        return None

    # Try regex first for common patterns
    regex_patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
        r"(?:be\/)([0-9A-Za-z_-]{11}).*",
        r"(?:embed\/)([0-9A-Za-z_-]{11}).*",
        r"(?:shorts\/)([0-9A-Za-z_-]{11}).*",
    ]

    for pattern in regex_patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    # Fallback to robust URL parsing
    try:
        parsed = urlparse(url)
        if parsed.hostname == "youtu.be":
            return parsed.path[1:]
        if parsed.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
            if parsed.path == "/watch":
                return parse_qs(parsed.query).get("v", [None])[0]
            if parsed.path.startswith(("/embed/", "/v/", "/shorts/")):
                return parsed.path.split("/")[2]
    except Exception:
        pass

    return None


class Tools:
    class Valves(BaseModel):
        CITATION: Annotated[
            bool, Field(description="Enable or disable source citation tracking")
        ] = True
        YOUTUBE_COOKIES: Annotated[
            str,
            Field(
                description="Optional: Paste Netscape formatted YouTube cookies here to avoid bot detection."
            ),
        ] = ""

    class UserValves(BaseModel):
        TRANSCRIPT_LANGUAGE: Annotated[
            str,
            Field(
                description="Priority list of languages (comma-separated, e.g., 'en,en_auto')"
            ),
        ] = "en,en_auto"
        TRANSCRIPT_TRANSLATE: Annotated[
            str,
            Field(
                description="Target language for auto-translation if original is unavailable"
            ),
        ] = "en"
        GET_VIDEO_DETAILS: Annotated[
            bool, Field(description="Fetch video title and uploader name")
        ] = True

    def __init__(self):
        self.valves = self.Valves()
        self.citation = self.valves.CITATION

    async def _emit_status(
        self,
        __event_emitter__: Optional[Callable[[dict], Any]],
        description: str,
        done: bool = False,
        status: str = "in_progress",
    ):
        """Helper to emit status updates to the UI."""
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": description,
                        "status": status,
                        "done": done,
                    },
                }
            )

    async def get_youtube_transcript(
        self,
        url: str,
        __user__: dict = {},
        __event_emitter__: Optional[Callable[[dict], Any]] = None,
    ) -> str:
        """
        Retrieves the full transcript and basic metadata for a YouTube video.
        Use this tool whenever a user provides a YouTube link and asks for a summary or transcript.

        :param url: The full YouTube video URL.
        :return: A string containing the video title, author, and transcript content.
        """
        user_valves = __user__.get("valves", self.UserValves())

        try:
            video_id = extract_video_id(url)
            if not video_id:
                raise ValueError(f"Could not extract a valid video ID from: {url}")

            # Rick Roll check - a little Easter egg 🎸
            if video_id == "dQw4w9WgXcQ":
                return "Rick Roll detected! I'm never gonna give you that transcript, never gonna let you down... 😉"

            await self._emit_status(__event_emitter__, f"Searching for video {video_id}...")

            title, author = "", ""
            if user_valves.GET_VIDEO_DETAILS:
                loop = asyncio.get_running_loop()
                # Use extract_flat=True for much faster metadata-only retrieval
                ydl_opts = {"quiet": True, "no_warnings": True, "extract_flat": True}

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = await loop.run_in_executor(
                        None, functools.partial(ydl.extract_info, url, download=False)
                    )
                    title = info.get("title", "")
                    author = info.get("uploader", "")

                if title:
                    await self._emit_status(__event_emitter__, f"Found: {title}")

            await self._emit_status(__event_emitter__, "Retrieving transcript...")

            languages = [
                lang.strip() for lang in user_valves.TRANSCRIPT_LANGUAGE.split(",")
            ]

            loop = asyncio.get_running_loop()
            try:
                # Offload blocking API calls to thread pool
                transcript_list: TranscriptList = await loop.run_in_executor(
                    None, YouTubeTranscriptApi.list_transcripts, video_id
                )

                try:
                    # Attempt to find one of the preferred languages
                    transcript_data = transcript_list.find_transcript(languages)
                except Exception:
                    # Fallback to translation if enabled
                    if user_valves.TRANSCRIPT_TRANSLATE:
                        # Find ANY transcript and translate it
                        original = next(iter(transcript_list))
                        transcript_data = original.translate(user_valves.TRANSCRIPT_TRANSLATE)
                    else:
                        raise RuntimeError(
                            f"Transcript not found in preferred languages ({', '.join(languages)})."
                        )

                transcript_pieces = await loop.run_in_executor(
                    None, transcript_data.fetch
                )
                content = "\n".join([p["text"] for p in transcript_pieces])

            except Exception as e:
                raise RuntimeError(f"Transcript service error: {str(e)}")

            # Formatting the final output
            header = []
            if title:
                header.append(f"Title: {title}")
            if author:
                header.append(f"Uploader: {author}")

            output = "\n".join(header) + "\n\n" + content if header else content

            await self._emit_status(
                __event_emitter__,
                f"Transcript retrieved for '{title or video_id}'",
                done=True,
                status="success",
            )
            return output

        except Exception as e:
            error_msg = f"YouTube Tool Error: {str(e)}"
            await self._emit_status(__event_emitter__, error_msg, done=True, status="error")
            return error_msg
