"""
Kiyomi Streaming Progress - Real-time progress updates via Telegram message editing

Features:
- Edit messages in place to show progress
- Meaningful milestone updates (not spam)
- Visual progress indicators
- Collapse verbose output into summaries
"""
import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Callable, Any

from telegram import Message, Bot
from telegram.error import TelegramError

import pytz
from config import TIMEZONE

logger = logging.getLogger(__name__)

# Progress update configuration
MIN_UPDATE_INTERVAL = 1.5  # Minimum seconds between message edits
MAX_MESSAGE_LENGTH = 4000  # Telegram limit with buffer


@dataclass
class ProgressState:
    """Tracks the state of a streaming progress message."""
    message: Optional[Message] = None
    chat_id: Optional[int] = None
    last_update_time: float = 0
    current_text: str = ""
    phase: str = "starting"  # starting, reading, analyzing, fixing, building, deploying, done
    steps_completed: List[str] = field(default_factory=list)
    current_action: str = ""
    has_error: bool = False
    final_result: Optional[str] = None


class StreamingProgress:
    """
    Manages real-time progress streaming to Telegram.

    Usage:
        async with StreamingProgress(bot, chat_id) as progress:
            await progress.update("Reading files...")
            # do work
            await progress.update("Found the issue...")
            # do more work
            await progress.complete("Fixed and deployed!")
    """

    def __init__(self, bot: Bot, chat_id: int, initial_message: str = "🌸 Working on it..."):
        self.bot = bot
        self.chat_id = chat_id
        self.initial_message = initial_message
        self.state = ProgressState()
        self._update_lock = asyncio.Lock()

    async def __aenter__(self):
        """Send initial progress message."""
        try:
            self.state.message = await self.bot.send_message(
                chat_id=self.chat_id,
                text=self.initial_message
            )
            self.state.chat_id = self.chat_id
            self.state.current_text = self.initial_message
            self.state.last_update_time = asyncio.get_event_loop().time()
        except TelegramError as e:
            logger.error(f"Failed to send initial progress message: {e}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Finalize the progress message."""
        if exc_type is not None:
            # There was an error
            await self.error(f"Error: {exc_val}")
        return False

    async def update(self, text: str, phase: Optional[str] = None, force: bool = False) -> bool:
        """
        Update the progress message.

        Args:
            text: New status text
            phase: Optional phase update (reading, analyzing, fixing, etc.)
            force: Force update even if within min interval

        Returns:
            True if message was updated
        """
        async with self._update_lock:
            now = asyncio.get_event_loop().time()

            # Check if we should update (rate limiting)
            if not force and (now - self.state.last_update_time) < MIN_UPDATE_INTERVAL:
                return False

            if self.state.message is None:
                return False

            # Update phase if provided
            if phase:
                self.state.phase = phase

            # Build the progress message
            new_text = self._build_progress_text(text)

            # Don't update if text hasn't changed
            if new_text == self.state.current_text:
                return False

            try:
                await self.state.message.edit_text(new_text)
                self.state.current_text = new_text
                self.state.last_update_time = now
                return True
            except TelegramError as e:
                # Message might be too old to edit or unchanged
                if "message is not modified" not in str(e).lower():
                    logger.warning(f"Failed to edit progress message: {e}")
                return False

    async def add_step(self, step: str) -> bool:
        """Add a completed step to the progress."""
        self.state.steps_completed.append(step)
        return await self.update(step, force=True)

    async def set_action(self, action: str) -> bool:
        """Set the current action being performed."""
        self.state.current_action = action
        return await self.update(action)

    async def complete(self, result: str) -> bool:
        """Mark progress as complete with final result."""
        self.state.phase = "done"
        self.state.final_result = result

        # Build final message
        final_text = self._build_final_text(result)

        try:
            if self.state.message:
                await self.state.message.edit_text(final_text)
                self.state.current_text = final_text
                return True
        except TelegramError as e:
            logger.warning(f"Failed to edit final message: {e}")
            # Send as new message instead
            try:
                await self.bot.send_message(chat_id=self.chat_id, text=final_text)
                return True
            except:
                pass
        return False

    async def error(self, error_msg: str) -> bool:
        """Mark progress as failed with error."""
        self.state.has_error = True
        self.state.phase = "error"

        error_text = f"❌ {error_msg}"
        if self.state.steps_completed:
            error_text = "Steps completed:\n" + "\n".join(f"✓ {s}" for s in self.state.steps_completed[-3:]) + f"\n\n{error_text}"

        try:
            if self.state.message:
                await self.state.message.edit_text(error_text)
                return True
        except TelegramError:
            pass
        return False

    def _build_progress_text(self, current_status: str) -> str:
        """Build the progress message text."""
        # Phase emoji
        phase_emoji = {
            "starting": "🌸",
            "reading": "📖",
            "analyzing": "🔍",
            "fixing": "🔧",
            "building": "🔨",
            "deploying": "🚀",
            "testing": "🧪",
            "done": "✅",
            "error": "❌"
        }

        emoji = phase_emoji.get(self.state.phase, "🌸")

        # Build message
        lines = [f"{emoji} **{self.state.phase.title()}**"]

        # Show recent completed steps (last 3)
        if self.state.steps_completed:
            for step in self.state.steps_completed[-3:]:
                lines.append(f"  ✓ {step}")

        # Current action
        if current_status:
            lines.append(f"  → {current_status}")

        return "\n".join(lines)

    def _build_final_text(self, result: str) -> str:
        """Build the final completion message."""
        lines = ["✅ **Done**"]

        # Show key steps
        if self.state.steps_completed:
            lines.append("")
            for step in self.state.steps_completed[-5:]:  # Last 5 steps
                lines.append(f"  ✓ {step}")

        # Add result (truncated if needed)
        lines.append("")
        if len(result) > 500:
            lines.append(result[:500] + "...")
        else:
            lines.append(result)

        full_text = "\n".join(lines)

        # Ensure we don't exceed Telegram limits
        if len(full_text) > MAX_MESSAGE_LENGTH:
            return full_text[:MAX_MESSAGE_LENGTH-3] + "..."

        return full_text


def parse_claude_output_for_progress(line: str) -> Optional[dict]:
    """
    Parse a line of Claude CLI output and extract progress information.

    Returns dict with:
        - phase: current phase
        - step: completed step (if any)
        - action: current action
        - is_significant: whether this warrants an update
    """
    line = line.strip()
    if not line:
        return None

    result = {
        "phase": None,
        "step": None,
        "action": None,
        "is_significant": False
    }

    # File reading
    if re.search(r'(?:Reading|Read)\s+[`"]?([^`"\n]+)', line):
        match = re.search(r'(?:Reading|Read)\s+[`"]?([^`"\n]+)', line)
        filename = match.group(1).split('/')[-1]
        result["phase"] = "reading"
        result["action"] = f"Reading {filename}"
        result["is_significant"] = True
        return result

    # File writing/editing
    if re.search(r'(?:Writing|Wrote|Editing|Edit|Created)\s+[`"]?([^`"\n]+)', line):
        match = re.search(r'(?:Writing|Wrote|Editing|Edit|Created)\s+[`"]?([^`"\n]+)', line)
        filename = match.group(1).split('/')[-1]
        result["phase"] = "fixing"
        result["step"] = f"Updated {filename}"
        result["is_significant"] = True
        return result

    # Building
    if "npm run build" in line.lower() or "building" in line.lower():
        result["phase"] = "building"
        result["action"] = "Building project..."
        result["is_significant"] = True
        return result

    # Deploying
    if "vercel" in line.lower() or "deploying" in line.lower():
        result["phase"] = "deploying"
        result["action"] = "Deploying..."
        result["is_significant"] = True
        return result

    # Git operations
    if "git commit" in line.lower():
        result["step"] = "Committed changes"
        result["is_significant"] = True
        return result

    if "git push" in line.lower():
        result["step"] = "Pushed to remote"
        result["is_significant"] = True
        return result

    # Errors
    if "error" in line.lower() and len(line) < 100:
        result["action"] = line[:60]
        result["is_significant"] = True
        return result

    # Success indicators
    if any(s in line.lower() for s in ["success", "deployed", "completed", "✓", "✅"]):
        result["step"] = line[:50]
        result["is_significant"] = True
        return result

    # URL detection (deployment result)
    url_match = re.search(r'https?://[^\s]+\.vercel\.app[^\s]*', line)
    if url_match:
        result["step"] = f"Live at {url_match.group()}"
        result["is_significant"] = True
        return result

    return None


async def create_streaming_callback(progress: StreamingProgress) -> Callable:
    """
    Create a callback function for use with execute_claude.
    This parses output and updates the streaming progress.
    """
    async def callback(line: str):
        parsed = parse_claude_output_for_progress(line)
        if parsed and parsed.get("is_significant"):
            if parsed.get("phase"):
                progress.state.phase = parsed["phase"]
            if parsed.get("step"):
                await progress.add_step(parsed["step"])
            elif parsed.get("action"):
                await progress.set_action(parsed["action"])

    return callback
