# ElevenLabs Text-to-Speech Action

Convert assistant messages to natural-sounding speech using ElevenLabs TTS with flexible voice selection.

## Setup

1. Get an API key from [ElevenLabs](https://elevenlabs.io)
2. Add your API key to the action's Valves (settings)
3. (Optional) Set your preferred audio format in `AUDIO_FORMAT` (mp3, wav, pcm_16000, or ulaw_8000)
4. (Optional) Set your preferred default voice in the `DEFAULT_VOICE` setting

## Adding Custom Voices

Configure exactly which voices you want to use:

1. Open the action settings (Valves)
2. Find the `CUSTOM_VOICES` field
3. Add voices in this format: `VoiceName:VoiceID:Description` (one per line)

Example:
```
Donovan:DMyrgzQFny3JI1Y1paM5:Articulate, Strong and Deep
Jessica Anne Bogart:g6xIsTj2HwM6VR4iXFCw:Friendly and Conversational
Mark:1SM7GgM6IMuvQlz2BwM3:ConvoAI
```

**Result:** Only these voices will be shown in the selection dialog - nothing else.

**Where to find Voice IDs:**
1. Log into [ElevenLabs](https://elevenlabs.io)
2. Go to **Voices** → **My Voices**
3. Click the voice you want
4. Copy the **Voice ID** (long string like `DMyrgzQFny3JI1Y1paM5`)
5. Add it to `CUSTOM_VOICES` in the action settings with a description

## Audio Format

### Changing File Format

By default, the action generates **MP3 files**, but you can change this:

1. Open the action settings (Valves)
2. Find the `AUDIO_FORMAT` field
3. Choose your preferred format:
   - **mp3** (default) - Good compression, widely compatible
   - **wav** - Uncompressed, highest quality, larger files
   - **pcm_16000** - Raw PCM format, 16kHz sample rate
   - **ulaw_8000** - Compressed PCM format, 8kHz sample rate

Example: To use WAV format, set `AUDIO_FORMAT` to `wav`

## Voice Selection

### How It Works

The action displays **ALL voices** that are available in your ElevenLabs account, organized as:
- **Popular Voices** (with helpful descriptions) - the most commonly used voices
- **Other Available Voices** - any additional voices you have access to

The available voices vary depending on your ElevenLabs subscription plan and which voices you have access to.

### Why You Might Not See All Voices

Voices are only available if:
- Your ElevenLabs subscription tier includes them
- You've added them to your voice library
- Your API key has permission to use them

**View your available voices:**
1. Log into [ElevenLabs](https://elevenlabs.io)
2. Go to **Voices** section
3. See your full list of available voices

**To add more voices:**
1. Go to [ElevenLabs Voices](https://elevenlabs.io/voices)
2. Upgrade your subscription tier for more voice options
3. Or clone voices using voice cloning feature (Premium+)

### Setting a Default Voice

1. Open the action settings (Valves)
2. Set `DEFAULT_VOICE` to any voice from your available list
3. Example: If you see "Roger" in the dialog, set `DEFAULT_VOICE` to "Roger"
4. Now that voice will be pre-selected every time you use the action

**Important:** The default voice must exist in your account. If you set a voice that doesn't exist, the action will fallback to your first available voice and show a debug message.

### Voice Case Sensitivity

- Voice names are case-insensitive
- "Rachel", "rachel", and "RACHEL" all work
- The dialog shows the exact names available in your account

## Available Voices (Common Accounts)

If you have access to premium voices, you might see:
- **Roger** - Laid-back, casual, resonant
- **Sarah** - Mature, reassuring, confident
- **Laura** - Enthusiast, quirky attitude
- **Charlie** - Deep, confident, energetic
- **George** - Warm, captivating storyteller

## Troubleshooting

### "Invalid voice selection" Error

**Cause:** The voice you typed doesn't exactly match an available voice.

**Solution:** 
1. Copy the exact name from the dialog
2. Paste it into the input field
3. Action is case-insensitive, so capitalization doesn't matter

### Default Voice Not Being Used

**Cause:** The `DEFAULT_VOICE` setting doesn't match any voice in your account.

**Solution:**
1. Check which voices appear in the dialog
2. Update `DEFAULT_VOICE` to match one of them exactly
3. Restart the action

### No Voices Showing

**Cause:** API key issue or no voices in your account.

**Solution:**
1. Verify your ElevenLabs API key is correct
2. Check that your ElevenLabs account has voices available
3. Check your subscription tier

## Voice Descriptions

When available in your account, popular voices are:

- **Rachel** - Friendly and approachable, casual settings
- **Adam** - Deep authoritative narrator, viral storytelling
- **Bella** - Warm and empathetic, emotional support
- **Antoni** - Calm news anchor style, documentaries
- **Domi** - Playful and versatile, children's content

For more voices and options, visit [ElevenLabs Voice Library](https://elevenlabs.io)

## Requirements

- Valid ElevenLabs API key
- At least one voice in your ElevenLabs account
- Open WebUI 0.3.10+

## Features

- Uses your default voice for quick one-click generation
- Easy voice switching by copy-pasting from the dialog
- Case-insensitive voice matching
- Clear error messages with available voices
- Async operation with timeouts to prevent hanging
