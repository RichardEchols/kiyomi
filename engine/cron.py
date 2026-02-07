"""
Kiyomi — Cron Task Engine
Scheduled automation that actually DOES work, not just sends reminders.

"Every Monday at 9am, check my portfolio and give me a summary"
→ Kiyomi runs Claude with that prompt, sends the result to Telegram.

Different from reminders: reminders send a text. Cron tasks run AI.
"""
import json
import logging
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from engine.config import CONFIG_DIR

logger = logging.getLogger("kiyomi.cron")

CRON_FILE = CONFIG_DIR / "cron.json"


# ── Persistence ──────────────────────────────────────────────

def _load_crons() -> list[dict]:
    """Load all cron tasks from disk."""
    if CRON_FILE.exists():
        try:
            with open(CRON_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load cron.json: {e}")
    return []


def _save_crons(crons: list[dict]):
    """Save all cron tasks to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CRON_FILE, "w") as f:
        json.dump(crons, f, indent=2)


# ── Natural Language Schedule Parsing ────────────────────────

# Maps natural language to (hour, minute, weekday_or_none, interval_hours)
# weekday: 0=Mon, 6=Sun. None means every day. interval_hours for "every N hours".
_SCHEDULE_PATTERNS: list[tuple[str, dict]] = [
    # Specific days
    (r"every\s+monday(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?", {"weekday": 0}),
    (r"every\s+tuesday(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?", {"weekday": 1}),
    (r"every\s+wednesday(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?", {"weekday": 2}),
    (r"every\s+thursday(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?", {"weekday": 3}),
    (r"every\s+friday(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?", {"weekday": 4}),
    (r"every\s+saturday(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?", {"weekday": 5}),
    (r"every\s+sunday(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?", {"weekday": 6}),
    # Time of day
    (r"every\s+morning(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?", {"default_hour": 8}),
    (r"every\s+afternoon(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?", {"default_hour": 14}),
    (r"every\s+evening(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?", {"default_hour": 18}),
    (r"every\s+night(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?", {"default_hour": 21}),
    # Generic daily
    (r"every\s+day(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?", {"default_hour": 9}),
    (r"daily(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?", {"default_hour": 9}),
    # Interval hours
    (r"every\s+(\d+)\s*hours?", {"interval": True}),
    (r"every\s+(\d+)\s*minutes?", {"interval_minutes": True}),
    # Just a time: "at 9am", "at 3:30pm"
    (r"(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)", {"time_only": True, "default_hour": 9}),
]


def parse_schedule(text: str) -> Optional[dict]:
    """Parse natural language schedule into a schedule descriptor.

    Returns dict with keys:
        - schedule_human: str  (human-readable version)
        - next_run: str        (ISO datetime of next fire)
        - _type: "daily" | "weekly" | "interval"
        - _hour, _minute: int
        - _weekday: int or None
        - _interval_seconds: int or None

    Returns None if unparseable.
    """
    text_lower = text.lower().strip()
    now = datetime.now()

    for pattern, meta in _SCHEDULE_PATTERNS:
        match = re.search(pattern, text_lower)
        if not match:
            continue

        groups = match.groups()
        hour = meta.get("default_hour", 9)
        minute = 0
        weekday = meta.get("weekday")

        # Handle interval patterns
        if meta.get("interval"):
            interval_hours = int(groups[0])
            next_run = now + timedelta(hours=interval_hours)
            return {
                "schedule_human": f"every {interval_hours} hour{'s' if interval_hours != 1 else ''}",
                "next_run": next_run.isoformat(timespec="seconds"),
                "_type": "interval",
                "_hour": None,
                "_minute": None,
                "_weekday": None,
                "_interval_seconds": interval_hours * 3600,
            }

        if meta.get("interval_minutes"):
            interval_minutes = int(groups[0])
            next_run = now + timedelta(minutes=interval_minutes)
            return {
                "schedule_human": f"every {interval_minutes} minute{'s' if interval_minutes != 1 else ''}",
                "next_run": next_run.isoformat(timespec="seconds"),
                "_type": "interval",
                "_hour": None,
                "_minute": None,
                "_weekday": None,
                "_interval_seconds": interval_minutes * 60,
            }

        # Extract time from capture groups
        if groups and groups[0] is not None:
            hour = int(groups[0])
            if len(groups) > 1 and groups[1] is not None:
                minute = int(groups[1])
            if len(groups) > 2 and groups[2] is not None:
                ampm = groups[2].lower()
                if ampm == "pm" and hour != 12:
                    hour += 12
                elif ampm == "am" and hour == 12:
                    hour = 0
            else:
                # No AM/PM specified — infer
                if hour <= 6:
                    hour += 12  # "at 3" → 3 PM

        # Calculate next_run
        next_run = _calculate_next_run(now, hour, minute, weekday)

        # Build human-readable
        time_str = _format_time(hour, minute)
        if weekday is not None:
            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            human = f"every {day_names[weekday]} at {time_str}"
            stype = "weekly"
        else:
            human = f"every day at {time_str}"
            stype = "daily"

        return {
            "schedule_human": human,
            "next_run": next_run.isoformat(timespec="seconds"),
            "_type": stype,
            "_hour": hour,
            "_minute": minute,
            "_weekday": weekday,
            "_interval_seconds": None,
        }

    return None


def _calculate_next_run(now: datetime, hour: int, minute: int, weekday: Optional[int]) -> datetime:
    """Calculate the next datetime this schedule should fire."""
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if weekday is not None:
        # Find next occurrence of this weekday
        days_ahead = weekday - now.weekday()
        if days_ahead < 0:
            days_ahead += 7
        elif days_ahead == 0 and target <= now:
            days_ahead = 7
        target += timedelta(days=days_ahead)
    else:
        # Daily — if already past today's time, schedule for tomorrow
        if target <= now:
            target += timedelta(days=1)

    return target


def _format_time(hour: int, minute: int) -> str:
    """Format 24h time as '8:00 AM' style."""
    ampm = "AM" if hour < 12 else "PM"
    display_hour = hour % 12
    if display_hour == 0:
        display_hour = 12
    if minute:
        return f"{display_hour}:{minute:02d} {ampm}"
    return f"{display_hour} {ampm}"


# ── CRUD ─────────────────────────────────────────────────────

def add_cron(task: str, schedule_str: str) -> Optional[dict]:
    """Add a new cron task from a natural language schedule.

    Returns the created cron entry or None if schedule can't be parsed.
    """
    schedule = parse_schedule(schedule_str)
    if not schedule:
        return None

    now = datetime.now()
    entry = {
        "id": uuid.uuid4().hex[:12],
        "task": task,
        "schedule_human": schedule["schedule_human"],
        "active": True,
        "created": now.isoformat(timespec="seconds"),
        "last_run": None,
        "next_run": schedule["next_run"],
        # Internal scheduling metadata
        "_type": schedule["_type"],
        "_hour": schedule.get("_hour"),
        "_minute": schedule.get("_minute"),
        "_weekday": schedule.get("_weekday"),
        "_interval_seconds": schedule.get("_interval_seconds"),
    }

    crons = _load_crons()
    crons.append(entry)
    _save_crons(crons)

    logger.info(f"Cron added: '{task[:50]}' — {schedule['schedule_human']} (next: {schedule['next_run']})")
    return entry


def remove_cron(cron_id: str) -> bool:
    """Remove (deactivate) a cron task by ID."""
    crons = _load_crons()
    found = False
    for c in crons:
        if c["id"] == cron_id:
            c["active"] = False
            found = True
            break

    if found:
        _save_crons(crons)
        logger.info(f"Cron deactivated: {cron_id}")
    return found


def delete_cron(cron_id: str) -> bool:
    """Permanently delete a cron task by ID."""
    crons = _load_crons()
    new_crons = [c for c in crons if c["id"] != cron_id]
    if len(new_crons) < len(crons):
        _save_crons(new_crons)
        logger.info(f"Cron deleted: {cron_id}")
        return True
    return False


def list_crons() -> list[dict]:
    """Return all active cron tasks."""
    return [c for c in _load_crons() if c.get("active", True)]


def get_due_crons(now: datetime) -> list[dict]:
    """Return cron tasks that should fire now (within a 60-second window)."""
    crons = _load_crons()
    due = []

    for c in crons:
        if not c.get("active", True):
            continue

        next_run_str = c.get("next_run")
        if not next_run_str:
            continue

        try:
            next_run = datetime.fromisoformat(next_run_str)
        except (ValueError, TypeError):
            continue

        # Fire if next_run is within 60 seconds of now (or past due)
        delta = (now - next_run).total_seconds()
        if -30 <= delta <= 90:  # small window: 30s early to 90s late
            due.append(c)

    return due


def mark_cron_run(cron_id: str, now: datetime):
    """Mark a cron as having just run; recalculate next_run."""
    crons = _load_crons()

    for c in crons:
        if c["id"] != cron_id:
            continue

        c["last_run"] = now.isoformat(timespec="seconds")

        cron_type = c.get("_type", "daily")

        if cron_type == "interval":
            interval = c.get("_interval_seconds", 3600)
            c["next_run"] = (now + timedelta(seconds=interval)).isoformat(timespec="seconds")

        elif cron_type == "weekly":
            hour = c.get("_hour", 9)
            minute = c.get("_minute", 0)
            weekday = c.get("_weekday", 0)
            # Next week, same day/time
            next_run = _calculate_next_run(now, hour, minute, weekday)
            c["next_run"] = next_run.isoformat(timespec="seconds")

        else:  # daily
            hour = c.get("_hour", 9)
            minute = c.get("_minute", 0)
            # Tomorrow at same time
            tomorrow = now + timedelta(days=1)
            next_run = tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
            c["next_run"] = next_run.isoformat(timespec="seconds")

        break

    _save_crons(crons)
