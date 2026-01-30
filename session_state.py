"""
Kiyomi Session State - Track context across messages

This module tracks:
- Current project being worked on
- Recent errors discussed
- What was just deployed
- Conversation context
"""
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
import pytz

from config import BASE_DIR, TIMEZONE

logger = logging.getLogger(__name__)

# State persistence file
STATE_FILE = BASE_DIR / "session_state.json"


@dataclass
class SessionState:
    """Current session state."""
    current_project: Optional[str] = None  # Project ID
    current_project_name: Optional[str] = None  # Project name
    last_error_discussed: Optional[str] = None
    last_deploy_url: Optional[str] = None
    last_deploy_time: Optional[str] = None
    last_activity: Optional[str] = None
    recent_topics: List[str] = None
    context_notes: List[str] = None

    def __post_init__(self):
        if self.recent_topics is None:
            self.recent_topics = []
        if self.context_notes is None:
            self.context_notes = []


# Global state instance
_state: Optional[SessionState] = None


def _load_state() -> SessionState:
    """Load state from file."""
    global _state

    if _state is not None:
        return _state

    try:
        if STATE_FILE.exists():
            data = json.loads(STATE_FILE.read_text())
            _state = SessionState(**data)
            logger.info("Session state loaded from file")
        else:
            _state = SessionState()
            logger.info("Created new session state")
    except Exception as e:
        logger.error(f"Error loading session state: {e}")
        _state = SessionState()

    return _state


def _save_state():
    """Save state to file."""
    if _state is None:
        return

    try:
        STATE_FILE.write_text(json.dumps(asdict(_state), indent=2))
    except Exception as e:
        logger.error(f"Error saving session state: {e}")


def get_state() -> SessionState:
    """Get current session state."""
    return _load_state()


# ============================================
# STATE UPDATES
# ============================================

def set_current_project(project_id: str, project_name: str):
    """Set the current project being worked on."""
    state = _load_state()
    state.current_project = project_id
    state.current_project_name = project_name
    state.last_activity = datetime.now(pytz.timezone(TIMEZONE)).isoformat()
    _save_state()
    logger.info(f"Set current project: {project_name}")


def clear_current_project():
    """Clear the current project."""
    state = _load_state()
    state.current_project = None
    state.current_project_name = None
    _save_state()


def get_current_project() -> Optional[str]:
    """Get the current project ID."""
    state = _load_state()
    return state.current_project


def get_current_project_name() -> Optional[str]:
    """Get the current project name."""
    state = _load_state()
    return state.current_project_name


def set_last_error(error_description: str):
    """Set the last error that was discussed."""
    state = _load_state()
    state.last_error_discussed = error_description[:500]  # Truncate
    state.last_activity = datetime.now(pytz.timezone(TIMEZONE)).isoformat()
    _save_state()


def get_last_error() -> Optional[str]:
    """Get the last error discussed."""
    state = _load_state()
    return state.last_error_discussed


def set_last_deploy(url: str):
    """Record a deployment."""
    state = _load_state()
    state.last_deploy_url = url
    state.last_deploy_time = datetime.now(pytz.timezone(TIMEZONE)).isoformat()
    state.last_activity = datetime.now(pytz.timezone(TIMEZONE)).isoformat()
    _save_state()
    logger.info(f"Recorded deployment: {url}")


def get_last_deploy() -> Dict[str, Optional[str]]:
    """Get last deployment info."""
    state = _load_state()
    return {
        "url": state.last_deploy_url,
        "time": state.last_deploy_time
    }


def add_topic(topic: str):
    """Add a topic to recent topics."""
    state = _load_state()
    if topic not in state.recent_topics:
        state.recent_topics.insert(0, topic)
        state.recent_topics = state.recent_topics[:10]  # Keep last 10
    _save_state()


def get_recent_topics() -> List[str]:
    """Get recent topics discussed."""
    state = _load_state()
    return state.recent_topics


def add_context_note(note: str):
    """Add a context note for this session."""
    state = _load_state()
    tz = pytz.timezone(TIMEZONE)
    timestamp = datetime.now(tz).strftime("%H:%M")
    state.context_notes.insert(0, f"[{timestamp}] {note}")
    state.context_notes = state.context_notes[:20]  # Keep last 20
    _save_state()


def get_context_notes() -> List[str]:
    """Get context notes."""
    state = _load_state()
    return state.context_notes


def clear_context_notes():
    """Clear context notes (typically at session end)."""
    state = _load_state()
    state.context_notes = []
    _save_state()


# ============================================
# CONTEXT BUILDING
# ============================================

def build_session_context() -> str:
    """
    Build context string from session state for prompts.
    """
    state = _load_state()
    parts = []

    if state.current_project_name:
        parts.append(f"**Current Project:** {state.current_project_name}")

    if state.last_error_discussed:
        parts.append(f"**Recent Error:** {state.last_error_discussed[:100]}...")

    if state.last_deploy_url and state.last_deploy_time:
        parts.append(f"**Last Deploy:** {state.last_deploy_url} ({state.last_deploy_time[:16]})")

    if state.recent_topics:
        topics = ", ".join(state.recent_topics[:5])
        parts.append(f"**Recent Topics:** {topics}")

    if state.context_notes:
        notes = "\n".join(state.context_notes[:5])
        parts.append(f"**Notes:**\n{notes}")

    if not parts:
        return ""

    return "## Session Context\n\n" + "\n".join(parts)


# ============================================
# REFERENCE RESOLUTION
# ============================================

def resolve_reference(text: str) -> Optional[Dict[str, Any]]:
    """
    Resolve references like "it", "the app", "the error" to concrete things.

    Args:
        text: User message text

    Returns:
        Dict with resolved references or None
    """
    state = _load_state()
    text_lower = text.lower()

    resolved = {}

    # "Fix it", "deploy it", "check it" -> current project
    if any(phrase in text_lower for phrase in ["fix it", "deploy it", "check it", "the app", "the project"]):
        if state.current_project:
            resolved["project"] = state.current_project
            resolved["project_name"] = state.current_project_name

    # "The error", "that error", "this issue" -> last error
    if any(phrase in text_lower for phrase in ["the error", "that error", "this issue", "the issue", "the problem"]):
        if state.last_error_discussed:
            resolved["error"] = state.last_error_discussed

    # "The deployment", "the site" -> last deploy
    if any(phrase in text_lower for phrase in ["the deployment", "the site", "the url"]):
        if state.last_deploy_url:
            resolved["deploy_url"] = state.last_deploy_url

    return resolved if resolved else None


def is_continuation(text: str) -> bool:
    """
    Check if this message is a continuation of previous context.
    """
    text_lower = text.lower().strip()

    continuation_phrases = [
        "fix it", "deploy it", "check it", "try again",
        "what about", "and also", "also", "now",
        "the same", "again", "still", "another",
    ]

    return any(phrase in text_lower for phrase in continuation_phrases)


# ============================================
# SESSION LIFECYCLE
# ============================================

def start_session():
    """Called when a new session starts (e.g., morning)."""
    state = _load_state()
    state.context_notes = []
    state.recent_topics = []
    _save_state()
    logger.info("Session started")


def end_session() -> str:
    """
    Called when session ends. Returns summary.
    """
    state = _load_state()

    summary_parts = []

    if state.current_project_name:
        summary_parts.append(f"Worked on: {state.current_project_name}")

    if state.last_deploy_url:
        summary_parts.append(f"Last deploy: {state.last_deploy_url}")

    if state.recent_topics:
        summary_parts.append(f"Topics: {', '.join(state.recent_topics[:5])}")

    # Clear session-specific state but keep project context
    state.context_notes = []

    _save_state()
    logger.info("Session ended")

    return "\n".join(summary_parts) if summary_parts else "No significant activity"


def get_session_duration() -> Optional[timedelta]:
    """Get how long the current session has been active."""
    state = _load_state()
    if not state.last_activity:
        return None

    try:
        last = datetime.fromisoformat(state.last_activity)
        now = datetime.now(pytz.timezone(TIMEZONE))
        return now - last
    except:
        return None
