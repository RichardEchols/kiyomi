#!/usr/bin/env python3
"""
Kiyomi v5.0 — Multi-CLI Telegram Bridge
Telegram message → CLI subprocess → response back to Telegram.
Works with Claude CLI, Codex CLI, and Gemini CLI.
~300 lines. No bloat.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Add engine dir to path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)
from telegram.constants import ChatAction

from engine.config import load_config, save_config, CONFIG_DIR, IDENTITY_FILE, WORKSPACE
from engine.cli_adapter import get_adapter, sync_identity_file, get_env, detect_available_clis
from engine.updater import check_for_updates, perform_update, restart_bot

logger = logging.getLogger("kiyomi.bot")

# --- Session tracking ---
# {chat_id: session_id} — persist CLI sessions per chat
SESSIONS_FILE = CONFIG_DIR / "sessions.json"


def _load_sessions() -> dict:
    if SESSIONS_FILE.exists():
        try:
            with open(SESSIONS_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _save_sessions(sessions: dict):
    try:
        with open(SESSIONS_FILE, "w") as f:
            json.dump(sessions, f, indent=2)
    except (IOError, OSError) as e:
        logger.warning(f"Failed to save sessions: {e}")


sessions = _load_sessions()


# --- File detection ---
def _find_new_files(workspace: Path, since: float) -> list[Path]:
    """Find files created in workspace since timestamp."""
    new_files = []
    skip = {
        "CLAUDE.md", "AGENTS.md", "GEMINI.md", "identity.md",
        "sessions.json", "config.json", "cron.json", "reminders.json",
        "relationships.json", "habits.json", "kiyomi.lock",
    }
    skip_ext = {".log", ".lock", ".pid"}
    for item in workspace.iterdir():
        if item.name.startswith(".") or item.name in skip:
            continue
        if item.suffix in skip_ext:
            continue
        if item.is_dir():
            continue
        if item.is_file() and item.stat().st_mtime > since:
            new_files.append(item)
    return new_files


# --- Telegram Handlers ---

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    config = load_config()
    name = config.get("name", "there")
    cli = config.get("cli") or config.get("provider") or "your AI"

    # Lock to this user on first contact
    if not config.get("telegram_user_id") and update.effective_user:
        config["telegram_user_id"] = str(update.effective_user.id)
        save_config(config)

    await update.message.reply_text(
        f"Hey {name}! I'm Kiyomi, your AI assistant powered by {cli.title()}.\n\n"
        f"Just send me a message and I'll respond. Send photos and I'll analyze them.\n\n"
        f"Tips:\n"
        f"- /reset — Start a fresh conversation\n"
        f"- /cli — Switch AI provider\n"
        f"- /identity — View/edit your assistant's personality\n"
        f"- /update — Check for Kiyomi updates"
    )


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset conversation session."""
    chat_id = str(update.effective_chat.id)
    if chat_id in sessions:
        del sessions[chat_id]
        _save_sessions(sessions)
    await update.message.reply_text("Fresh start! Previous conversation context cleared.")


async def cmd_cli(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Switch CLI provider."""
    config = load_config()
    current = config.get("cli") or config.get("provider") or "none"
    available = detect_available_clis()

    lines = [f"Current CLI: **{current}**\n", "Available CLIs:"]
    for name, path in available.items():
        marker = " (active)" if name == current else ""
        lines.append(f"  - {name}{marker}")

    if not available:
        lines.append("  None found! Install Claude, Codex, or Gemini CLI.")

    lines.append(f"\nTo switch, send: /cli <name>")
    lines.append(f"Example: /cli gemini")

    # Check if user provided an argument
    if context.args:
        new_cli = context.args[0].lower().strip()
        if new_cli in available:
            config["cli"] = new_cli
            save_config(config)
            sync_identity_file(new_cli, WORKSPACE)
            # Clear session since different CLI
            chat_id = str(update.effective_chat.id)
            if chat_id in sessions:
                del sessions[chat_id]
                _save_sessions(sessions)
            await update.message.reply_text(f"Switched to **{new_cli}** CLI! Session reset.")
            return
        elif new_cli in ("claude", "codex", "gemini"):
            await update.message.reply_text(f"{new_cli} CLI is not installed on this machine.")
            return

    try:
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception:
        await update.message.reply_text("\n".join(lines))


async def cmd_identity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show or describe the current identity file."""
    if IDENTITY_FILE.exists():
        content = IDENTITY_FILE.read_text(encoding="utf-8", errors="replace")
        # Truncate for Telegram
        if len(content) > 3500:
            content = content[:3500] + "\n\n... (truncated)"
        try:
            await update.message.reply_text(
                f"**Your assistant's identity:**\n\n```\n{content}\n```\n\n"
                f"To change it, just tell me in plain English what you want me to do differently.",
                parse_mode="Markdown"
            )
        except Exception:
            # Markdown failed (e.g., backticks in identity content) — send plain text
            await update.message.reply_text(
                f"Your assistant's identity:\n\n{content}\n\n"
                f"To change it, just tell me in plain English what you want me to do differently."
            )
    else:
        await update.message.reply_text("No identity file found. Send me a message to get started!")


async def cmd_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check for updates."""
    await update.message.reply_text("Checking for updates...")
    try:
        info = await check_for_updates()
        if info.get("available"):
            await update.message.reply_text(
                f"Update available: v{info.get('latest', '?')}\n"
                f"{info.get('changes', '')}\n\n"
                f"Downloading and installing..."
            )
            result = await perform_update()
            if result.get("success"):
                await update.message.reply_text(
                    f"Update installed! {result.get('message', '')}\nRestarting..."
                )
                await restart_bot()
            else:
                await update.message.reply_text(f"Update failed: {result.get('message', 'Unknown error')}")
        else:
            await update.message.reply_text(
                f"You're on the latest version! ({info.get('current', '?')})"
            )
    except Exception as e:
        logger.error(f"Update check failed: {e}", exc_info=True)
        await update.message.reply_text(
            "Couldn't check for updates right now. "
            "Make sure you have an internet connection and try again later."
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all text and media messages — the core loop."""
    config = load_config()
    chat_id = str(update.effective_chat.id)

    # Auth check: only allow the configured user (or anyone if not set)
    allowed_user = config.get("telegram_user_id", "")
    if allowed_user:
        if not update.effective_user:
            # Channel posts or anonymous messages — reject
            return
        if str(update.effective_user.id) != allowed_user:
            await update.message.reply_text("Sorry, this bot is private.")
            return

    # Get CLI adapter (support both v5 "cli" and v4 "provider" field names)
    cli_name = config.get("cli") or config.get("provider") or ""
    if not cli_name:
        await update.message.reply_text(
            "No AI CLI configured. Open Kiyomi settings to set up your AI provider."
        )
        return

    try:
        adapter = get_adapter(cli_name)
    except ValueError as e:
        await update.message.reply_text(
            f"Your AI provider ({cli_name}) isn't recognized. "
            f"Use /cli to switch to a supported provider (claude, codex, or gemini)."
        )
        return
    except FileNotFoundError as e:
        await update.message.reply_text(
            f"The {cli_name} CLI isn't installed on this machine. "
            f"Use /cli to switch providers, or install it from the setup wizard."
        )
        return

    # Build the message text
    message_text = update.message.text or update.message.caption or ""

    # Track all temp files for cleanup
    temp_files = []

    # Handle photos
    image_path = None
    if update.message.photo:
        photo = update.message.photo[-1]  # Highest resolution
        photo_file = await photo.get_file()
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False, dir=str(WORKSPACE))
        tmp.close()  # Close before download_to_drive writes to it
        await photo_file.download_to_drive(tmp.name)
        image_path = tmp.name
        temp_files.append(tmp.name)
        if not message_text:
            message_text = "Describe this image in detail."

    # Handle documents (PDFs, etc.)
    if update.message.document:
        doc = update.message.document
        doc_file = await doc.get_file()
        ext = Path(doc.file_name).suffix if doc.file_name else ".bin"
        tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False, dir=str(WORKSPACE))
        tmp.close()  # Close before download_to_drive writes to it
        await doc_file.download_to_drive(tmp.name)
        temp_files.append(tmp.name)
        if not message_text:
            message_text = f"Analyze this file: {tmp.name}"
        else:
            message_text = f"{message_text}\n\nFile saved at: {tmp.name}"

    # Handle voice messages
    if update.message.voice:
        voice = update.message.voice
        voice_file = await voice.get_file()
        tmp = tempfile.NamedTemporaryFile(suffix=".ogg", delete=False, dir=str(WORKSPACE))
        tmp.close()  # Close before download_to_drive writes to it
        await voice_file.download_to_drive(tmp.name)
        temp_files.append(tmp.name)
        message_text = f"Transcribe and respond to this voice message: {tmp.name}"

    if not message_text:
        return

    # Show typing indicator
    await update.message.chat.send_action(ChatAction.TYPING)

    # Sync identity file before calling CLI
    sync_identity_file(cli_name, WORKSPACE)

    # Build and run CLI command
    session_id = sessions.get(chat_id)
    model = config.get("model") or None
    timeout = config.get("cli_timeout", 120)

    try:
        cmd = adapter.build_command(
            message=message_text,
            session_id=session_id,
            model=model,
            image_path=image_path,
        )
    except FileNotFoundError as e:
        # Clean up temp files before returning
        for tmp_path in temp_files:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        await update.message.reply_text(
            f"The {cli_name} CLI isn't installed. "
            f"Use /cli to switch to a different AI provider, or reinstall it."
        )
        return

    logger.info(f"[{cli_name}] Running: {' '.join(cmd[:4])}...")
    before = time.time()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(WORKSPACE),
            env=get_env(),
        )
        elapsed = time.time() - before
        logger.info(f"[{cli_name}] Completed in {elapsed:.1f}s (rc={result.returncode})")

        response_text, new_session_id = adapter.parse_response(
            result.stdout, result.stderr, result.returncode
        )

        # Update session
        if new_session_id:
            sessions[chat_id] = new_session_id
            _save_sessions(sessions)

    except subprocess.TimeoutExpired:
        response_text = f"The AI took too long to respond (>{timeout}s timeout). Try a shorter message or /reset."
    except Exception as e:
        logger.error(f"CLI error: {e}", exc_info=True)
        response_text = (
            f"Something went wrong while talking to {cli_name}. "
            f"Try again, or use /reset to start a fresh conversation. "
            f"If this keeps happening, try /cli to switch AI providers."
        )

    # Clean up all temp files (photos, documents, voice)
    for tmp_path in temp_files:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    # Send response (split if too long for Telegram)
    if not response_text:
        response_text = "(No response from AI)"

    # Telegram max message length is 4096
    for chunk in _split_message(response_text):
        try:
            await update.message.reply_text(chunk, parse_mode="Markdown")
        except Exception:
            # Markdown parse failed — send as plain text
            await update.message.reply_text(chunk)

    # Check for new files in workspace
    new_files = _find_new_files(WORKSPACE, before)
    for f in new_files[:5]:  # Max 5 files
        try:
            if f.stat().st_size < 10_000_000:  # <10MB
                with open(f, "rb") as fh:
                    await update.message.reply_document(document=fh, filename=f.name)
        except Exception as e:
            logger.warning(f"Failed to send file {f.name}: {e}")


def _split_message(text: str, max_len: int = 4000) -> list[str]:
    """Split a message into chunks that fit Telegram's limit."""
    if len(text) <= max_len:
        return [text]
    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        # Try to split at a newline first
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            # No newline — try splitting at a space to avoid mid-word breaks
            split_at = text.rfind(" ", 0, max_len)
        if split_at == -1:
            # No space either — hard split at max_len
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


# --- App Builder ---

def _build_app() -> Application | None:
    """Build the Telegram Application."""
    config = load_config()
    token = config.get("telegram_token", "")
    if not token:
        logger.error("No Telegram token configured")
        return None

    app = Application.builder().token(token).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("cli", cmd_cli))
    app.add_handler(CommandHandler("identity", cmd_identity))
    app.add_handler(CommandHandler("update", cmd_update))

    # All messages
    app.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO | filters.Document.ALL | filters.VOICE,
        handle_message
    ))

    return app


# --- Entry Points ---

def main():
    """Run the bot (blocking, with signal handlers)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    config = load_config()
    if not config.get("telegram_token"):
        logger.error("No Telegram token. Run onboarding first.")
        sys.exit(1)

    cli_name = config.get("cli") or config.get("provider")
    if not cli_name:
        logger.error("No CLI configured. Run onboarding first.")
        sys.exit(1)

    logger.info(f"Kiyomi v5.0 starting — CLI: {cli_name}")
    app = _build_app()
    app.run_polling(drop_pending_updates=True)


# Module-level stop event and loop reference for clean shutdown from app.py
_stop_event: asyncio.Event | None = None
_engine_loop: asyncio.AbstractEventLoop | None = None


def request_stop():
    """Request the threaded engine to stop gracefully.

    Safe to call from any thread. The engine's async loop will
    pick up the event and shut down the Telegram polling.
    """
    global _stop_event, _engine_loop
    if _stop_event and _engine_loop and _engine_loop.is_running():
        _engine_loop.call_soon_threadsafe(_stop_event.set)


def main_threaded():
    """Start the bot from a background thread (no signal handlers).

    Used when running inside the PyInstaller menu bar app.
    """
    global _stop_event, _engine_loop

    app = _build_app()
    if not app:
        raise RuntimeError("No Telegram token configured")

    config = load_config()
    cli_name = config.get("cli") or config.get("provider") or "?"
    logger.info(f"Kiyomi v5.0 starting (threaded) — CLI: {cli_name}")

    async def _run():
        global _stop_event
        _stop_event = asyncio.Event()
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        logger.info("Kiyomi is running! Waiting for messages...")
        try:
            await _stop_event.wait()
        finally:
            logger.info("Shutting down Telegram polling...")
            await app.updater.stop()
            await app.stop()
            await app.shutdown()

    _engine_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_engine_loop)
    try:
        _engine_loop.run_until_complete(_run())
    finally:
        _engine_loop.close()
        _engine_loop = None
        _stop_event = None


if __name__ == "__main__":
    main()
