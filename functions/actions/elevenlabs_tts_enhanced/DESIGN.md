# ElevenLabs TTS, Enhanced native attachment

## Intent

This is a low-risk improvement of the existing ElevenLabs action. It uses only
public Open WebUI action, file-storage, and event contracts, and does not need
a frontend or backend Open WebUI change.

## Interaction

1. The action generates an MP3, stores it as a private Open WebUI file, and
   emits the documented short `files` event. Open WebUI persists that event on
   the assistant message.
2. The normal Open WebUI file chip opens its native file modal. The **Preview**
   tab plays the MP3. The existing filename/download affordance handles saving.
3. The action writes a compact explanation into `FileForm.data.content` so the
   stock modal's unavoidable **Content** tab explains the audio controls rather
   than displaying `No content` for a binary MP3.
4. The assistant response is updated in place with brief instructions and a
   direct MP3 link as a secondary path. The original assistant answer remains
   intact.

## Why this is intentionally small

The stock FileItem modal renders both Content and Preview tabs for audio. A
function cannot hide or relabel that UI without modifying Open WebUI. Providing
accurate descriptive content is the smallest compatible way to make the fixed
Content tab useful.

## Source contracts

- Open WebUI event documentation specifies that `files` persists file
  attachments to the chat record; `chat:message:files` is only an in-memory UI
  alias.
- Open WebUI actions can return a `messages` update for the active assistant
  message.
- The stored file uses `FileForm`, `Files.insert_new_file`, and
  `Storage.upload_file`, matching current Open WebUI server APIs.
