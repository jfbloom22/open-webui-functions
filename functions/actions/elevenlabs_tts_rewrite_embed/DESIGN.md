# Embedded player variant

## Approach

This is a complete function-only alternative to Open WebUI's file modal. It emits the documented, persistent `embeds` event containing an HTML audio card. The card has the native browser player first and a visibly labeled **Download MP3** button second, so there is no empty `Content` tab or filename-click discovery problem.

The MP3 is base64-encoded in the saved iframe HTML. JavaScript turns it into a `Blob` object URL inside the sandboxed iframe, then supplies that URL to both the player and a download anchor. No request to `/api/v1/files/{id}/content` is required.

## Why this is meaningfully different

Open WebUI's file route relies on an Authorization header from the parent app's local storage. A normal navigation, Markdown link, or default sandboxed iframe cannot provide that header. Rich UI embeds are persisted and receive `allow-scripts` and `allow-downloads`, making self-contained audio the only function-only embed design that does not depend on parent authentication state.

## UX

- The player renders directly above the assistant message.
- The primary controls are playback and a labeled `Download MP3` button.
- It avoids attaching a binary Open WebUI file, so users never see the misleading `Content` / `Preview` modal.
- The message text confirms that the controls are directly above it.

## Deliberate limitations

- The audio bytes are stored in chat history, so this is intentionally capped at 2.5 MB by default. It is a short-form narration option, not the long-audio default.
- Content in the chat DOM is recoverable by anyone with access to that chat. This aligns with the approved low-sensitivity, publicly-shareable audio use case, but it is not a private-file delivery mechanism.
- Open WebUI documents that sandboxed iframe downloads can be unreliable on iOS. This variation is designed to be compared with the native-file action, whose title/download route remains the better fallback for that environment.

## Source basis

This implementation follows Open WebUI's current Event and Rich UI Embedding documentation: short-name `embeds` events persist to the database; action embeds render above message text; embeds support scripts and downloads; and embeds should report height with `iframe:height`. The documentation also confirms the authentication and sandbox constraints that make a relative protected file URL unsuitable here.

The current version also emits a main-page `execute` event that creates a visible
Download MP3 control outside the sandbox. This addresses browsers that render
the embedded player but block its iframe-initiated download.
