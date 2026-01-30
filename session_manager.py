"""
Kiyomi Session Manager - Perfect conversation continuity

Features:
- Track active work sessions
- "Continue" command support
- Context preservation across conversations
- Smart session resumption
"""
import asyncio
import logging
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any

import pytz
from config import BASE_DIR, TIMEZONE, WORKSPACE_DIR

logger = logging.getLogger(__name__)

# Session configuration
SESSION_FILE = BASE_DIR / "active_session.json"
SESSION_HISTORY_FILE = BASE_DIR / "session_history.json"
SESSION_TIMEOUT_HOURS = 4  # Session expires after 4 hours of inactivity
MAX_SESSION_HISTORY = 20


@dataclass
class WorkSession:
    """Represents an active work session."""
    session_id: str
    started_at: datetime
    last_activity: datetime

    # What we're working on
    current_project: Optional[str] = None
    current_task: Optional[str] = None
    task_context: Optional[str] = None

    # Conversation state
    messages: List[Dict[str, str]] = field(default_factory=list)  # Last N messages
    pending_action: Optional[str] = None  # Action waiting for confirmation

    # Work progress
    files_modified: List[str] = field(default_factory=list)
    steps_completed: List[str] = field(default_factory=list)
    last_result: Optional[str] = None
    last_error: Optional[str] = None

    # Flags
    is_active: bool = True
    needs_continuation: bool = False
    was_interrupted: bool = False


# Global session state
_current_session: Optional[WorkSession] = None


def _get_session_id() -> str:
    """Generate a unique session ID."""
    tz = pytz.timezone(TIMEZONE)
    return datetime.now(tz).strftime("%Y%m%d_%H%M%S")


def _load_session() -> Optional[WorkSession]:
    """Load the current session from file."""
    try:
        if SESSION_FILE.exists():
            with open(SESSION_FILE) as f:
                data = json.load(f)

            # Convert datetime strings back to datetime objects
            data["started_at"] = datetime.fromisoformat(data["started_at"])
            data["last_activity"] = datetime.fromisoformat(data["last_activity"])

            return WorkSession(**data)
    except Exception as e:
        logger.error(f"Error loading session: {e}")
    return None


def _save_session(session: WorkSession) -> None:
    """Save the current session to file."""
    try:
        data = asdict(session)
        # Convert datetime to ISO format
        data["started_at"] = session.started_at.isoformat()
        data["last_activity"] = session.last_activity.isoformat()

        with open(SESSION_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving session: {e}")


def _archive_session(session: WorkSession) -> None:
    """Archive a completed session to history."""
    try:
        history = []
        if SESSION_HISTORY_FILE.exists():
            with open(SESSION_HISTORY_FILE) as f:
                history = json.load(f)

        # Add session summary
        summary = {
            "session_id": session.session_id,
            "started_at": session.started_at.isoformat(),
            "ended_at": session.last_activity.isoformat(),
            "project": session.current_project,
            "task": session.current_task,
            "steps_completed": len(session.steps_completed),
            "files_modified": session.files_modified[:5]
        }

        history.append(summary)
        history = history[-MAX_SESSION_HISTORY:]

        with open(SESSION_HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)

    except Exception as e:
        logger.error(f"Error archiving session: {e}")


def get_current_session() -> Optional[WorkSession]:
    """Get the current active session."""
    global _current_session

    if _current_session is None:
        _current_session = _load_session()

    if _current_session:
        # Check if session has expired
        tz = pytz.timezone(TIMEZONE)
        now = datetime.now(tz)

        # Make last_activity timezone-aware if it isn't
        last_activity = _current_session.last_activity
        if last_activity.tzinfo is None:
            last_activity = tz.localize(last_activity)

        if now - last_activity > timedelta(hours=SESSION_TIMEOUT_HOURS):
            # Session expired - archive it
            _archive_session(_current_session)
            _current_session = None
            if SESSION_FILE.exists():
                SESSION_FILE.unlink()

    return _current_session


def start_session(task: str, project: Optional[str] = None) -> WorkSession:
    """Start a new work session."""
    global _current_session

    # Archive old session if exists
    if _current_session:
        _archive_session(_current_session)

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    _current_session = WorkSession(
        session_id=_get_session_id(),
        started_at=now,
        last_activity=now,
        current_task=task,
        current_project=project
    )

    _save_session(_current_session)
    return _current_session


def update_session(
    task: Optional[str] = None,
    project: Optional[str] = None,
    message: Optional[Dict[str, str]] = None,
    step_completed: Optional[str] = None,
    file_modified: Optional[str] = None,
    result: Optional[str] = None,
    error: Optional[str] = None,
    context: Optional[str] = None
) -> Optional[WorkSession]:
    """Update the current session with new information."""
    global _current_session

    session = get_current_session()
    if session is None:
        # Start new session if none exists
        session = start_session(task or "General task", project)

    tz = pytz.timezone(TIMEZONE)
    session.last_activity = datetime.now(tz)

    if task:
        session.current_task = task
    if project:
        session.current_project = project
    if context:
        session.task_context = context
    if message:
        session.messages.append(message)
        # Keep last 10 messages
        session.messages = session.messages[-10:]
    if step_completed:
        session.steps_completed.append(step_completed)
        session.steps_completed = session.steps_completed[-20:]  # Keep last 20
    if file_modified and file_modified not in session.files_modified:
        session.files_modified.append(file_modified)
        session.files_modified = session.files_modified[-10:]  # Keep last 10
    if result:
        session.last_result = result[:1000]  # Truncate
        session.last_error = None
    if error:
        session.last_error = error[:500]

    _save_session(session)
    _current_session = session
    return session


def mark_interrupted() -> None:
    """Mark the current session as interrupted (e.g., timeout, cancel)."""
    session = get_current_session()
    if session:
        session.was_interrupted = True
        session.needs_continuation = True
        _save_session(session)


def mark_needs_continuation(reason: Optional[str] = None) -> None:
    """Mark that the current task needs to be continued."""
    session = get_current_session()
    if session:
        session.needs_continuation = True
        if reason:
            session.pending_action = reason
        _save_session(session)


def end_session() -> None:
    """End the current session."""
    global _current_session

    session = get_current_session()
    if session:
        session.is_active = False
        _archive_session(session)
        _current_session = None
        if SESSION_FILE.exists():
            SESSION_FILE.unlink()


def get_continuation_context() -> Optional[str]:
    """
    Get context for continuing the current session.
    Returns a formatted string for injection into prompts.
    """
    session = get_current_session()
    if session is None:
        return None

    context_parts = []

    # Header
    context_parts.append("## Session Context (Continuing from earlier)")

    # What we were working on
    if session.current_task:
        context_parts.append(f"**Task:** {session.current_task}")
    if session.current_project:
        context_parts.append(f"**Project:** {session.current_project}")

    # Progress so far
    if session.steps_completed:
        context_parts.append("\n**Completed:**")
        for step in session.steps_completed[-5:]:
            context_parts.append(f"  ✓ {step}")

    # Files we touched
    if session.files_modified:
        context_parts.append(f"\n**Files modified:** {', '.join(session.files_modified[-5:])}")

    # Last result or error
    if session.last_error:
        context_parts.append(f"\n**Last error:** {session.last_error}")
    elif session.last_result:
        context_parts.append(f"\n**Last result:** {session.last_result[:200]}...")

    # What needs to be done
    if session.pending_action:
        context_parts.append(f"\n**Pending:** {session.pending_action}")
    elif session.was_interrupted:
        context_parts.append("\n**Status:** Task was interrupted - needs to be resumed")
    elif session.needs_continuation:
        context_parts.append("\n**Status:** Task needs continuation")

    # Recent conversation
    if session.messages:
        context_parts.append("\n**Recent conversation:**")
        for msg in session.messages[-3:]:
            role = "Richard" if msg.get("role") == "user" else "Kiyomi"
            content = msg.get("content", "")[:100]
            context_parts.append(f"  {role}: {content}...")

    return "\n".join(context_parts)


def should_continue() -> bool:
    """Check if there's a session that should be continued."""
    session = get_current_session()
    if session is None:
        return False

    return session.needs_continuation or session.was_interrupted


def get_session_summary() -> Optional[str]:
    """Get a brief summary of the current session for the user."""
    session = get_current_session()
    if session is None:
        return None

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    # Calculate duration
    last_activity = session.last_activity
    if last_activity.tzinfo is None:
        last_activity = tz.localize(last_activity)

    minutes_ago = int((now - last_activity).total_seconds() / 60)

    summary = f"**Current Session**\n"
    if session.current_project:
        summary += f"Project: {session.current_project}\n"
    if session.current_task:
        summary += f"Task: {session.current_task[:50]}...\n"
    summary += f"Steps completed: {len(session.steps_completed)}\n"
    summary += f"Last activity: {minutes_ago} minutes ago\n"

    if session.needs_continuation:
        summary += "\n⚠️ **Task needs continuation**"
        if session.pending_action:
            summary += f"\nPending: {session.pending_action}"

    return summary


def is_continue_command(text: str) -> bool:
    """Check if user message is a continue command."""
    text_lower = text.lower().strip()
    continue_phrases = [
        "continue",
        "keep going",
        "go on",
        "proceed",
        "resume",
        "pick up where we left off",
        "where were we",
        "what were we doing",
        "carry on"
    ]
    return any(phrase in text_lower for phrase in continue_phrases)


def get_continue_prompt() -> Optional[str]:
    """Get the prompt to continue the current session."""
    session = get_current_session()
    if session is None:
        return None

    prompt_parts = ["Continue with the previous task."]

    if session.pending_action:
        prompt_parts.append(f"Specifically: {session.pending_action}")
    elif session.last_error:
        prompt_parts.append(f"Last error was: {session.last_error}. Fix it and continue.")
    elif session.current_task:
        prompt_parts.append(f"The task was: {session.current_task}")

    return " ".join(prompt_parts)
