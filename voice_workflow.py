"""
Kiyomi Voice Workflow - Complete voice-to-voice interaction

Features:
- Transcribe voice messages
- Process commands
- Respond with voice (TTS)
"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Optional, Tuple
import subprocess

from config import BASE_DIR, WORKSPACE_DIR

logger = logging.getLogger(__name__)

# Voice configuration
TEMP_DIR = BASE_DIR / "temp"
TEMP_DIR.mkdir(exist_ok=True)


async def transcribe_voice(audio_path: Path) -> Tuple[bool, str]:
    """
    Transcribe a voice message to text.

    Uses OpenAI Whisper via the CLI or API.
    Falls back to Claude's description if Whisper not available.

    Returns (success, transcription_or_error)
    """
    try:
        # Try using whisper CLI first
        whisper_result = await _try_whisper_cli(audio_path)
        if whisper_result[0]:
            return whisper_result

        # Try using OpenAI API
        openai_result = await _try_openai_whisper(audio_path)
        if openai_result[0]:
            return openai_result

        # Fallback: Ask Claude to describe what might be said
        # (This is a placeholder - Claude can't actually hear audio)
        return False, "Voice transcription not available. Please type your message."

    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return False, f"Transcription failed: {e}"


async def _try_whisper_cli(audio_path: Path) -> Tuple[bool, str]:
    """Try transcription using whisper CLI."""
    try:
        # Check if whisper is installed
        result = await asyncio.create_subprocess_exec(
            "which", "whisper",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await result.communicate()

        if result.returncode != 0:
            return False, "Whisper CLI not installed"

        # Convert ogg to wav if needed
        wav_path = audio_path.with_suffix('.wav')
        if audio_path.suffix == '.ogg':
            convert = await asyncio.create_subprocess_exec(
                "ffmpeg", "-i", str(audio_path), "-ar", "16000", "-ac", "1", str(wav_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await convert.communicate()
            if convert.returncode != 0:
                return False, "Audio conversion failed"
        else:
            wav_path = audio_path

        # Run whisper
        process = await asyncio.create_subprocess_exec(
            "whisper", str(wav_path),
            "--model", "base",
            "--output_format", "txt",
            "--output_dir", str(TEMP_DIR),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        await asyncio.wait_for(process.communicate(), timeout=60)

        # Read the output file
        txt_path = TEMP_DIR / f"{wav_path.stem}.txt"
        if txt_path.exists():
            transcription = txt_path.read_text().strip()
            txt_path.unlink()  # Clean up
            return True, transcription

        return False, "No transcription output"

    except asyncio.TimeoutError:
        return False, "Transcription timed out"
    except Exception as e:
        return False, str(e)


async def _try_openai_whisper(audio_path: Path) -> Tuple[bool, str]:
    """Try transcription using OpenAI Whisper API."""
    try:
        import openai

        # Load API key from env
        env_file = Path("/Users/richardecholsai2/Documents/Apps/.env.local")
        api_key = None

        if env_file.exists():
            content = env_file.read_text()
            for line in content.split('\n'):
                if line.startswith('OPENAI_API_KEY='):
                    api_key = line.split('=', 1)[1].strip().strip('"\'')
                    break

        if not api_key:
            return False, "OpenAI API key not found"

        client = openai.OpenAI(api_key=api_key)

        with open(audio_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )

        return True, transcription.text

    except ImportError:
        return False, "OpenAI package not installed"
    except Exception as e:
        return False, str(e)


async def voice_to_voice_workflow(
    audio_path: Path,
    execute_fn,  # execute_claude function
    tts_fn,      # quick_speak function
) -> Tuple[bool, str, Optional[Path]]:
    """
    Complete voice-to-voice workflow:
    1. Transcribe voice input
    2. Execute the command
    3. Generate voice response

    Returns (success, text_result, audio_path_or_none)
    """
    # Step 1: Transcribe
    transcribe_success, transcription = await transcribe_voice(audio_path)

    if not transcribe_success:
        return False, transcription, None

    logger.info(f"Transcribed voice: {transcription}")

    # Step 2: Execute
    result, success = await execute_fn(transcription)

    if not success:
        return False, result, None

    # Step 3: Generate voice response (for shorter responses)
    voice_path = None
    if len(result) < 500:  # Only TTS for short responses
        tts_success, tts_path = await tts_fn(result)
        if tts_success:
            voice_path = Path(tts_path)

    return True, result, voice_path


async def generate_voice_response(
    text: str,
    voice_id: Optional[str] = None
) -> Tuple[bool, Optional[Path]]:
    """
    Generate a voice response from text.
    Uses ElevenLabs or fallback TTS.
    """
    from voice import quick_speak

    success, path = await quick_speak(text)

    if success:
        return True, Path(path)
    return False, None


# ============================================
# VOICE MESSAGE DETECTION
# ============================================

def is_voice_request(text: str) -> bool:
    """Check if user is requesting voice response."""
    text_lower = text.lower()
    voice_triggers = [
        "speak",
        "say it",
        "tell me",
        "voice",
        "read it",
        "out loud",
        "audio"
    ]
    return any(trigger in text_lower for trigger in voice_triggers)


def should_respond_with_voice(
    original_was_voice: bool,
    response_length: int,
    user_preference: Optional[str] = None
) -> bool:
    """Determine if response should include voice."""
    # If original was voice, respond with voice
    if original_was_voice:
        return response_length < 500  # Only short responses

    # Check user preference
    if user_preference == "always_voice":
        return True
    if user_preference == "never_voice":
        return False

    return False
