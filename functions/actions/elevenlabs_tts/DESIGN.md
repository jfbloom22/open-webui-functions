# ElevenLabs TTS canonical action

## Approach

The action uses Open WebUI's documented `files` event and Files API. It uploads
the generated MP3 to the configured storage provider, adds a short explanatory
note as the file's text content, and attaches a normal `audio/mpeg` file record
to the assistant message.

## Why this is meaningfully different

The action forwards the authenticated request's Authorization header only to
Open WebUI's own `/api/v1/files/` endpoints. Open WebUI stores the bytes using
its configured local or S3 provider and enforces the current user's file access
permissions on later playback and download requests.

## UX

- The message receives one native audio-file attachment.
- The friendly filename identifies the voice, generation time, and unique suffix.
- The native Preview tab provides playback.
- The Content tab explains: “Select Preview to listen. To download the MP3,
  click the filename above.”
- Clicking the filename uses Open WebUI's authenticated download route.

## Deliberate limitations

- The audio bytes are stored by Open WebUI's configured file provider rather than
  in chat history, so hour-long episodes do not inflate message records.
- The small explanatory note is intentionally stored as file content so the
  native Content tab is useful instead of showing “No content.”
- File retention follows Open WebUI's configured storage and cleanup policy.

## Source basis

This implementation follows Open WebUI's current Events and Files API
documentation. Short-name `files` events persist file attachments on the
message, while `/api/v1/files/{id}/content` provides authenticated playback and
download. The action avoids `execute` and Rich UI iframe workarounds entirely.
