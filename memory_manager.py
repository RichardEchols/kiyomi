"""
Kiyomi Memory Manager - Persistent memory file operations
"""
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List
from config import (
    MEMORY_DIR, WORKSPACE_DIR, TIMEZONE,
    IDENTITY_FILE, SOUL_FILE, USER_FILE, MEMORY_FILE,
    COMMITMENTS_FILE, HEARTBEAT_FILE
)
import pytz

logger = logging.getLogger(__name__)


def get_today_date() -> str:
    """Get today's date in YYYY-MM-DD format (EST)."""
    tz = pytz.timezone(TIMEZONE)
    return datetime.now(tz).strftime("%Y-%m-%d")


def get_current_time() -> str:
    """Get current time in HH:MM format (EST)."""
    tz = pytz.timezone(TIMEZONE)
    return datetime.now(tz).strftime("%H:%M")


def get_today_memory_file() -> Path:
    """Get the path to today's memory file."""
    return MEMORY_DIR / f"{get_today_date()}.md"


def read_file(path: Path) -> Optional[str]:
    """Read a file's contents."""
    try:
        if path.exists():
            return path.read_text()
        return None
    except Exception as e:
        logger.error(f"Error reading {path}: {e}")
        return None


def write_file(path: Path, content: str) -> bool:
    """Write content to a file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return True
    except Exception as e:
        logger.error(f"Error writing {path}: {e}")
        return False


def append_to_file(path: Path, content: str) -> bool:
    """Append content to a file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as f:
            f.write(content)
        return True
    except Exception as e:
        logger.error(f"Error appending to {path}: {e}")
        return False


# ============================================
# WORKSPACE FILE OPERATIONS
# ============================================

def read_identity() -> Optional[str]:
    """Read IDENTITY.md."""
    return read_file(IDENTITY_FILE)


def read_soul() -> Optional[str]:
    """Read SOUL.md."""
    return read_file(SOUL_FILE)


def read_user() -> Optional[str]:
    """Read USER.md."""
    return read_file(USER_FILE)


def read_memory() -> Optional[str]:
    """Read MEMORY.md (long-term memory)."""
    return read_file(MEMORY_FILE)


def read_commitments() -> Optional[str]:
    """Read COMMITMENTS.md."""
    return read_file(COMMITMENTS_FILE)


def read_heartbeat() -> Optional[str]:
    """Read HEARTBEAT.md."""
    return read_file(HEARTBEAT_FILE)


def update_heartbeat(content: str) -> bool:
    """Update HEARTBEAT.md."""
    return write_file(HEARTBEAT_FILE, content)


# ============================================
# DAILY MEMORY OPERATIONS
# ============================================

def read_today_memory() -> Optional[str]:
    """Read today's memory file."""
    return read_file(get_today_memory_file())


def log_to_today(entry: str) -> bool:
    """Log an entry to today's memory file."""
    timestamp = get_current_time()
    formatted_entry = f"\n### {timestamp}\n{entry}\n"

    today_file = get_today_memory_file()

    # Initialize file if it doesn't exist
    if not today_file.exists():
        header = f"# Memory Log - {get_today_date()}\n\n"
        write_file(today_file, header)

    return append_to_file(today_file, formatted_entry)


def log_command(command: str, response: str, success: bool) -> bool:
    """Log a command and its response."""
    status = "✅" if success else "❌"
    entry = f"**Command:** {command[:200]}\n**Status:** {status}\n**Response:** {response[:500]}..."
    return log_to_today(entry)


# ============================================
# SESSION STARTUP
# ============================================

def load_session_context() -> dict:
    """Load all relevant files for session startup."""
    return {
        "identity": read_identity(),
        "soul": read_soul(),
        "user": read_user(),
        "commitments": read_commitments(),
        "memory": read_memory(),
        "today": read_today_memory(),
        "heartbeat": read_heartbeat(),
    }


def get_recent_memory_files(days: int = 3) -> List[str]:
    """Get content from recent memory files."""
    tz = pytz.timezone(TIMEZONE)
    today = datetime.now(tz)
    contents = []

    for i in range(days):
        date = today - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        file_path = MEMORY_DIR / f"{date_str}.md"
        content = read_file(file_path)
        if content:
            contents.append(f"## {date_str}\n{content}")

    return contents


