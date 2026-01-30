"""
Kiyomi Voice - Text-to-Speech with ElevenLabs

This module provides:
- TTS generation using ElevenLabs API
- Voice message sending via Telegram
- Multiple voice options
"""
import asyncio
import aiohttp
import logging
from pathlib import Path
from typing import Optional, Tuple
import tempfile
import os

from config import (
    ELEVENLABS_API_KEY,
    ELEVENLABS_VOICE_RICK,
    ELEVENLABS_VOICE_RICHARD,
    BASE_DIR
)

logger = logging.getLogger(__name__)

# ElevenLabs API
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"

# Voice settings
DEFAULT_VOICE_ID = ELEVENLABS_VOICE_RICHARD  # Use Richard's cloned voice
KEIKO_STABILITY = 0.5
KEIKO_SIMILARITY = 0.75
KEIKO_STYLE = 0.3

# Temp directory for audio files
VOICE_TEMP_DIR = BASE_DIR / "temp" / "voice"


async def generate_speech(
    text: str,
    voice_id: Optional[str] = None,
    output_path: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Generate speech from text using ElevenLabs.

    Args:
        text: Text to convert to speech
        voice_id: Voice ID to use (defaults to Richard's voice)
        output_path: Where to save the audio file

    Returns:
        Tuple of (success, path_or_error)
    """
    if not ELEVENLABS_API_KEY:
        return False, "ElevenLabs API key not configured"

    if not text or len(text.strip()) == 0:
        return False, "No text provided"

    # Truncate very long text
    if len(text) > 5000:
        text = text[:5000] + "..."

    voice_id = voice_id or DEFAULT_VOICE_ID

    # Create output path if not provided
    if not output_path:
        VOICE_TEMP_DIR.mkdir(parents=True, exist_ok=True)
        output_path = str(VOICE_TEMP_DIR / f"speech_{os.urandom(8).hex()}.mp3")

    url = f"{ELEVENLABS_API_URL}/{voice_id}"

    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }

    payload = {
        "text": text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {
            "stability": KEIKO_STABILITY,
            "similarity_boost": KEIKO_SIMILARITY,
            "style": KEIKO_STYLE,
            "use_speaker_boost": True
        }
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    error = await response.text()
                    logger.error(f"ElevenLabs API error: {error}")
                    return False, f"TTS API error: {response.status}"

                # Save audio to file
                audio_data = await response.read()
                with open(output_path, "wb") as f:
                    f.write(audio_data)

                logger.info(f"Generated speech: {len(audio_data)} bytes")
                return True, output_path

    except asyncio.TimeoutError:
        return False, "TTS request timed out"
    except Exception as e:
        logger.error(f"TTS generation error: {e}")
        return False, f"TTS error: {str(e)}"


async def text_to_voice_message(
    text: str,
    voice_id: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Convert text to a voice message file.

    This is a convenience wrapper around generate_speech.

    Args:
        text: Text to convert
        voice_id: Voice to use

    Returns:
        Tuple of (success, file_path_or_error)
    """
    return await generate_speech(text, voice_id)


def cleanup_voice_file(file_path: str):
    """Clean up a voice file after sending."""
    try:
        if file_path and Path(file_path).exists():
            Path(file_path).unlink()
            logger.debug(f"Cleaned up voice file: {file_path}")
    except Exception as e:
        logger.warning(f"Failed to clean up voice file: {e}")


def cleanup_old_voice_files(max_age_hours: int = 24):
    """Clean up old voice files."""
    try:
        if not VOICE_TEMP_DIR.exists():
            return

        import time
        now = time.time()
        max_age_seconds = max_age_hours * 3600

        for file in VOICE_TEMP_DIR.glob("*.mp3"):
            age = now - file.stat().st_mtime
            if age > max_age_seconds:
                file.unlink()
                logger.debug(f"Cleaned up old voice file: {file}")

    except Exception as e:
        logger.warning(f"Failed to clean up old voice files: {e}")


# ============================================
# VOICE OPTIONS
# ============================================

VOICE_OPTIONS = {
    "richard": ELEVENLABS_VOICE_RICHARD,
    "rick": ELEVENLABS_VOICE_RICK,
    "default": DEFAULT_VOICE_ID,
}


def get_voice_id(voice_name: str) -> str:
    """Get voice ID from name."""
    return VOICE_OPTIONS.get(voice_name.lower(), DEFAULT_VOICE_ID)


# ============================================
# QUICK TTS
# ============================================

async def quick_speak(text: str) -> Tuple[bool, str]:
    """
    Quick TTS with default settings.

    Args:
        text: Text to speak

    Returns:
        Tuple of (success, file_path_or_error)
    """
    # Clean up old files first
    cleanup_old_voice_files()

    return await generate_speech(text)


# ============================================
# INTEGRATION HELPERS
# ============================================

def should_use_voice(text: str) -> bool:
    """
    Determine if a response should be sent as voice.

    Currently: only for morning brief or if explicitly requested.
    """
    # Only use voice for specific scenarios
    # - Morning brief
    # - Explicit voice requests
    # - Very short confirmations

    # For now, return False - let the caller decide
    return False


async def send_voice_or_text(
    text: str,
    send_text_callback,
    send_voice_callback,
    use_voice: bool = False
) -> bool:
    """
    Send a message as either text or voice.

    Args:
        text: Message content
        send_text_callback: Async function to send text
        send_voice_callback: Async function to send voice file
        use_voice: Whether to use voice

    Returns:
        True if sent successfully
    """
    if not use_voice:
        await send_text_callback(text)
        return True

    success, result = await quick_speak(text)
    if success:
        try:
            await send_voice_callback(result)
            cleanup_voice_file(result)
            return True
        except Exception as e:
            logger.error(f"Failed to send voice: {e}")
            # Fall back to text
            await send_text_callback(text)
            return True
    else:
        # Fall back to text
        logger.warning(f"TTS failed, falling back to text: {result}")
        await send_text_callback(text)
        return True
