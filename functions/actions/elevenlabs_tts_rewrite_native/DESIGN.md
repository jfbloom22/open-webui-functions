# ElevenLabs TTS, native attachment variant

This variant intentionally uses only stock Open WebUI primitives. It does not
require a frontend patch or an extra server endpoint.

## Interaction contract

1. The action creates an MP3 in Open WebUI's normal file store, owned by the
   user who requested it.
2. It emits the *short* `files` event, not the legacy `chat:message:files`
   alias. Open WebUI persists only the short event name to the chat database,
   so the attachment remains present after a refresh.
3. The stored file contains a short `data.content` explanation. Stock Open
   WebUI renders that in the file modal's **Content** tab, which prevents a
   healthy binary audio attachment from looking like a failed text extraction.
4. The assistant message supplies a named `Download MP3` link and explains
   that the native attachment supports preview and download. This is a useful
   direct affordance where the browser can authenticate the normal file route;
   the native attachment remains the reliable, built-in fallback.

## Trade-offs

Stock Open WebUI's binary-file modal owns the exact placement of its preview
and download controls. A function cannot move those controls without modifying
Open WebUI. This design therefore prioritizes the persisted native attachment,
then adds a simple message-level link without relying on custom JavaScript,
public URLs, or security workarounds.

The implementation is a clean rewrite rather than a wrapper around the
existing action. Its small helper boundaries make the event and file contracts
testable without an Open WebUI runtime.

The current version also emits Open WebUI's documented `execute` event to place
a visible **Download MP3** control in the main page context. The native file
remains the durable Preview fallback.
