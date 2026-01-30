"""
Kiyomi Context - Prompt building, conversation history, context compaction
"""
import asyncio
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

import pytz

from config import (
    BASE_DIR, WORKSPACE_DIR, MEMORY_DIR, APPS_DIR, TIMEZONE,
    IDENTITY_FILE, USER_FILE, MEMORY_FILE, HEARTBEAT_FILE,
    CLAUDE_CLI_PATH, BOT_NAME, ENABLE_CHROME,
)

logger = logging.getLogger(__name__)

CONVERSATION_HISTORY_FILE = BASE_DIR / "conversation_history.json"
MAX_HISTORY = 50
MAX_MSG_LEN = 3000
MAX_CONTEXT_CHARS = 60000
PROJECTS_FILE = BASE_DIR / "projects.json"
PREFERENCES_FILE = BASE_DIR / "preferences.json"

# Active project tracking
_active_project: Optional[Dict] = None
_active_project_time: Optional[datetime] = None
_PROJECT_TIMEOUT = 1800  # 30 min inactivity clears project


# ── file helpers ──────────────────────────────────────────────

def _read(path: Path) -> Optional[str]:
    try:
        return path.read_text() if path.exists() else None
    except Exception as e:
        logger.error(f"Error reading {path}: {e}")
        return None


def _today_memory_path() -> Path:
    tz = pytz.timezone(TIMEZONE)
    return MEMORY_DIR / f"{datetime.now(tz).strftime('%Y-%m-%d')}.md"


# ── conversation history ──────────────────────────────────────

def _load_history() -> List[Dict]:
    try:
        if CONVERSATION_HISTORY_FILE.exists():
            with open(CONVERSATION_HISTORY_FILE) as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading history: {e}")
    return []


def _save_history(history: List[Dict]) -> None:
    try:
        tmp = CONVERSATION_HISTORY_FILE.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(history[-MAX_HISTORY:], f, indent=2)
        tmp.replace(CONVERSATION_HISTORY_FILE)
    except Exception as e:
        logger.error(f"Error saving history: {e}")
        # Fallback: try direct write
        try:
            with open(CONVERSATION_HISTORY_FILE, "w") as f:
                json.dump(history[-MAX_HISTORY:], f, indent=2)
        except Exception:
            pass


def get_last_assistant_message() -> Optional[str]:
    """Get the last assistant message from history."""
    history = _load_history()
    for msg in reversed(history):
        if msg["role"] == "assistant":
            return msg["content"]
    return None


def add_to_history(role: str, content: str) -> None:
    """Append a message to conversation_history.json (max 50)."""
    history = _load_history()
    tz = pytz.timezone(TIMEZONE)
    history.append({
        "role": role,
        "content": content[:MAX_MSG_LEN],
        "timestamp": datetime.now(tz).isoformat(),
    })
    _save_history(history)


def format_history_for_prompt() -> str:
    """Last 5 messages, truncated to 300 chars each."""
    history = _load_history()
    if not history:
        return ""
    recent = history[-5:]
    lines = ["## Recent Chat"]
    for msg in recent:
        role = "R" if msg["role"] == "user" else "K"
        text = msg["content"][:300]
        if len(msg["content"]) > 300:
            text += "..."
        lines.append(f"**{role}:** {text}\n")
    return "\n".join(lines)


# ── preferences / corrections ────────────────────────────────

def load_preferences() -> List[Dict]:
    """Load learned corrections from preferences.json."""
    try:
        if PREFERENCES_FILE.exists():
            with open(PREFERENCES_FILE) as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading preferences: {e}")
    return []


def save_correction(context: str, correction: str) -> None:
    """Save a user correction for future reference."""
    prefs = load_preferences()
    tz = pytz.timezone(TIMEZONE)
    prefs.append({
        "context": context[:200],
        "correction": correction[:300],
        "timestamp": datetime.now(tz).isoformat(),
    })
    prefs = prefs[-30:]  # Keep last 30
    try:
        tmp = PREFERENCES_FILE.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(prefs, f, indent=2)
        tmp.replace(PREFERENCES_FILE)
        logger.info(f"Saved correction: {correction[:80]}")
    except Exception as e:
        logger.error(f"Error saving correction: {e}")


# ── project context tracking ─────────────────────────────────

def get_active_project() -> Optional[Dict]:
    """Get currently active project (expires after 30 min)."""
    global _active_project, _active_project_time
    if _active_project and _active_project_time:
        tz = pytz.timezone(TIMEZONE)
        elapsed = (datetime.now(tz) - _active_project_time).total_seconds()
        if elapsed > _PROJECT_TIMEOUT:
            _active_project = None
            _active_project_time = None
    return _active_project


def set_active_project(project: Dict) -> None:
    """Set the currently active project."""
    global _active_project, _active_project_time
    _active_project = project
    _active_project_time = datetime.now(pytz.timezone(TIMEZONE))
    logger.info(f"Active project: {project.get('name', 'unknown')}")


# ── prompt builder ────────────────────────────────────────────

def build_prompt(user_message: str) -> str:
    """Build the full prompt: workspace context + daily memory + history + user message."""
    parts = []

    # Identity
    identity = _read(IDENTITY_FILE)
    if identity:
        parts.append(f"## Who You Are\n{identity}")

    # User preferences (inline — always the same)
    parts.append(
        "## About Richard (Quick Reference)\n"
        "- Just DO things, don't ask permission\n"
        "- Quick updates only, don't over-explain\n"
        "- Apple UI/UX aesthetic\n"
        "- Test locally before deploying\n"
        "- Use `vercel --prod --force`\n"
        "- Commit fixes with good messages"
    )

    # Learned corrections
    corrections = load_preferences()
    if corrections:
        corr_lines = ["## Things Richard Has Corrected"]
        for c in corrections[-5:]:
            corr_lines.append(f"- After: \"{c['context'][:80]}\" → \"{c['correction'][:100]}\"")
        parts.append("\n".join(corr_lines))

    # Active project context
    active = get_active_project()
    if active:
        parts.append(
            f"## Active Project Context\n"
            f"Currently working on: **{active.get('name', 'Unknown')}**\n"
            f"Path: `{active.get('path', APPS_DIR)}`\n"
            f"When Richard says vague things like 'fix the header', he means this project."
        )

    # Daily memory (today)
    today = _read(_today_memory_path())
    if today and len(today) < 4000:
        parts.append(f"## Today's Memory\n{today[:3000]}")

    # History
    history = format_history_for_prompt()
    if history:
        parts.append(history)

    # Capability guidance
    parts.append(
        f"## Your Capabilities\n"
        f"You have file tools AND browser tools. Use your judgment:\n\n"
        f"**Browser tools** — when Richard asks you to go to a URL, search the web, interact with a website.\n"
        f"**File / CLI tools** — coding, deploying, git, file management.\n"
        f"**Memory files** — write directly when asked to remember something:\n"
        f"- Daily: `{MEMORY_DIR}/YYYY-MM-DD.md`\n"
        f"- Long-term: `{MEMORY_FILE}`\n\n"
        f"**Opening apps**: Use `open -a \"AppName\"` via bash.\n"
        f"**Conversational**: If just chatting, respond without tools.\n\n"
        f"**Projects registry**: `{PROJECTS_FILE}` — read to find project paths.\n"
        f"**Apps dir**: `{APPS_DIR}`"
    )

    # Build final prompt
    context = "\n\n".join(parts)

    return (
        f"{context}\n\n---\n\n"
        f"You are {BOT_NAME}, Richard's AI assistant. Be direct and helpful. "
        f"Read files when you need more context.\n\n"
        f"**Richard:** {user_message}"
    )


# ── daily memory logging ──────────────────────────────────────

def log_to_daily(entry: str) -> None:
    """Append a one-liner to today's memory file."""
    try:
        tz = pytz.timezone(TIMEZONE)
        ts = datetime.now(tz).strftime("%H:%M")
        path = _today_memory_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(f"# Memory Log - {datetime.now(tz).strftime('%Y-%m-%d')}\n\n")
        with open(path, "a") as f:
            f.write(f"### {ts}\n{entry}\n\n")
    except Exception as e:
        logger.error(f"Error logging to daily memory: {e}")


# ── context compaction ────────────────────────────────────────

async def compact_if_needed() -> Optional[str]:
    """If history > 60K chars total, summarize via Claude and save to MEMORY.md."""
    history = _load_history()
    total = sum(len(m["content"]) for m in history)
    if total < MAX_CONTEXT_CHARS:
        return None

    history_text = format_history_for_prompt()
    compact_prompt = (
        "Summarize this conversation history into key points for long-term memory.\n"
        "Focus on: decisions made, preferences learned, tasks completed, important context.\n"
        "Keep it under 500 words.\n\n"
        f"{history_text}"
    )

    try:
        process = await asyncio.create_subprocess_exec(
            CLAUDE_CLI_PATH, "-p", compact_prompt, "--dangerously-skip-permissions",
            cwd=APPS_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=60)
        summary = stdout.decode("utf-8", errors="replace").strip()

        if summary:
            tz = pytz.timezone(TIMEZONE)
            date = datetime.now(tz).strftime("%Y-%m-%d %H:%M")

            # Append to MEMORY.md
            with open(MEMORY_FILE, "a") as f:
                f.write(f"\n\n---\n\n## Compacted Memory ({date})\n\n{summary}\n")

            # Also to daily memory
            daily = _today_memory_path()
            daily.parent.mkdir(parents=True, exist_ok=True)
            with open(daily, "a") as f:
                f.write(f"\n\n### Context Compaction ({date})\n{summary}\n")

            # Keep last 10 messages
            _save_history(history[-10:])
            logger.info("Context compacted and saved to memory")
            return summary
    except Exception as e:
        logger.error(f"Error compacting context: {e}")

    return None
