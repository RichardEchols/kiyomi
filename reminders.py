"""
Kiyomi Reminders System - Proactive notifications and follow-ups

Like ClawdBot, Kiyomi should proactively:
1. Remind Richard of scheduled tasks
2. Follow up on incomplete work
3. Nudge about commitments
4. Check in on long-running tasks
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Callable, List, Dict
import pytz

from config import TIMEZONE, BASE_DIR, WORKSPACE_DIR

logger = logging.getLogger(__name__)

# Reminders storage
REMINDERS_FILE = BASE_DIR / "reminders.json"


def _load_reminders() -> List[Dict]:
    """Load reminders from file."""
    try:
        if REMINDERS_FILE.exists():
            with open(REMINDERS_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading reminders: {e}")
    return []


def _save_reminders(reminders: List[Dict]) -> None:
    """Save reminders to file."""
    try:
        with open(REMINDERS_FILE, "w") as f:
            json.dump(reminders, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving reminders: {e}")


def add_reminder(
    message: str,
    remind_at: datetime,
    reminder_type: str = "custom",
    repeat: Optional[str] = None  # "daily", "weekly", None
) -> str:
    """
    Add a new reminder.

    Returns:
        Reminder ID
    """
    reminders = _load_reminders()

    reminder_id = f"rem_{int(datetime.now().timestamp())}"

    reminders.append({
        "id": reminder_id,
        "message": message,
        "remind_at": remind_at.isoformat(),
        "type": reminder_type,
        "repeat": repeat,
        "created": datetime.now().isoformat(),
        "sent": False
    })

    _save_reminders(reminders)
    return reminder_id


def remove_reminder(reminder_id: str) -> bool:
    """Remove a reminder by ID."""
    reminders = _load_reminders()
    original_len = len(reminders)
    reminders = [r for r in reminders if r["id"] != reminder_id]

    if len(reminders) < original_len:
        _save_reminders(reminders)
        return True
    return False


def list_reminders() -> List[Dict]:
    """Get all pending reminders."""
    reminders = _load_reminders()
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    # Filter to only pending reminders
    pending = []
    for r in reminders:
        remind_at = datetime.fromisoformat(r["remind_at"])
        if remind_at.tzinfo is None:
            remind_at = tz.localize(remind_at)

        if not r.get("sent", False) or r.get("repeat"):
            pending.append({
                **r,
                "remind_at_formatted": remind_at.strftime("%Y-%m-%d %H:%M"),
                "is_due": remind_at <= now
            })

    return sorted(pending, key=lambda x: x["remind_at"])


async def check_and_send_reminders(send_callback: Callable) -> int:
    """
    Check for due reminders and send them.

    Returns:
        Number of reminders sent
    """
    reminders = _load_reminders()
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    sent_count = 0
    updated_reminders = []

    for reminder in reminders:
        remind_at = datetime.fromisoformat(reminder["remind_at"])
        if remind_at.tzinfo is None:
            remind_at = tz.localize(remind_at)

        # Check if due and not already sent
        if remind_at <= now and not reminder.get("sent", False):
            # Send the reminder
            try:
                await send_callback(f"⏰ **Reminder:** {reminder['message']}")
                sent_count += 1
                logger.info(f"Sent reminder: {reminder['id']}")

                # Handle repeating reminders
                if reminder.get("repeat") == "daily":
                    # Schedule for tomorrow
                    new_remind_at = remind_at + timedelta(days=1)
                    reminder["remind_at"] = new_remind_at.isoformat()
                    reminder["sent"] = False
                    updated_reminders.append(reminder)
                elif reminder.get("repeat") == "weekly":
                    new_remind_at = remind_at + timedelta(weeks=1)
                    reminder["remind_at"] = new_remind_at.isoformat()
                    reminder["sent"] = False
                    updated_reminders.append(reminder)
                else:
                    # One-time reminder - mark as sent
                    reminder["sent"] = True
                    updated_reminders.append(reminder)

            except Exception as e:
                logger.error(f"Error sending reminder: {e}")
                updated_reminders.append(reminder)
        else:
            updated_reminders.append(reminder)

    _save_reminders(updated_reminders)
    return sent_count


async def check_commitments_and_followup(send_callback: Callable) -> None:
    """
    Check COMMITMENTS.md and follow up on pending items.
    """
    commitments_file = WORKSPACE_DIR / "COMMITMENTS.md"
    if not commitments_file.exists():
        return

    content = commitments_file.read_text()

    # Find pending items (unchecked)
    pending_items = []
    in_pending_section = False

    for line in content.split("\n"):
        if "## Pending Items" in line or "## Today's Agenda" in line:
            in_pending_section = True
            continue
        if line.startswith("## ") and in_pending_section:
            in_pending_section = False

        if in_pending_section and line.strip().startswith("- [ ]"):
            item = line.replace("- [ ]", "").strip()
            if item and item != "None currently":
                pending_items.append(item)

    if pending_items:
        tz = pytz.timezone(TIMEZONE)
        hour = datetime.now(tz).hour

        # Only send during working hours (9 AM - 9 PM)
        if 9 <= hour <= 21:
            msg = "📋 **Pending commitments:**\n"
            for item in pending_items[:5]:  # Max 5 items
                msg += f"• {item}\n"

            await send_callback(msg)


async def check_active_project_status(send_callback: Callable) -> None:
    """
    Check if active project needs attention.
    """
    active_project_file = WORKSPACE_DIR / "ACTIVE_PROJECT.md"
    if not active_project_file.exists():
        return

    content = active_project_file.read_text()

    # Check for incomplete status
    if "INCOMPLETE" in content.upper() or "IN PROGRESS" in content.upper():
        # Find project name
        project_name = "Unknown project"
        for line in content.split("\n"):
            if "**Name:**" in line:
                project_name = line.split("**Name:**")[1].strip()
                break

        # Check last activity timestamp
        last_activity = None
        for line in content.split("\n"):
            if line.startswith("### 202"):  # Timestamp format
                try:
                    timestamp_str = line.replace("###", "").strip()
                    last_activity = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M")
                    break
                except:
                    pass

        if last_activity:
            tz = pytz.timezone(TIMEZONE)
            now = datetime.now(tz)
            hours_since = (now.replace(tzinfo=None) - last_activity).total_seconds() / 3600

            # If no activity for 2+ hours during work time
            if hours_since > 2 and 9 <= now.hour <= 21:
                await send_callback(
                    f"🔨 **{project_name}** hasn't been touched in {int(hours_since)} hours. "
                    f"Need me to pick it back up?"
                )


async def start_reminder_scheduler(send_callback: Callable) -> None:
    """
    Start the reminder checking loop.
    Runs every minute to check for due reminders.
    """
    logger.info("Starting reminder scheduler...")

    check_cycle = 0

    while True:
        try:
            # Check reminders every minute
            sent = await check_and_send_reminders(send_callback)
            if sent > 0:
                logger.info(f"Sent {sent} reminders")

            check_cycle += 1

            # Every 30 minutes, check commitments and project status
            if check_cycle % 30 == 0:
                await check_commitments_and_followup(send_callback)

            # Every hour, check active project
            if check_cycle % 60 == 0:
                await check_active_project_status(send_callback)
                check_cycle = 0  # Reset to avoid overflow

        except Exception as e:
            logger.error(f"Reminder scheduler error: {e}")

        await asyncio.sleep(60)  # Check every minute


def parse_reminder_time(time_str: str) -> Optional[datetime]:
    """
    Parse natural language time strings.

    Examples:
        "in 30 minutes"
        "in 2 hours"
        "tomorrow at 9am"
        "at 3pm"
        "2024-01-28 14:00"
    """
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    time_str = time_str.lower().strip()

    # "in X minutes"
    if "in " in time_str and "minute" in time_str:
        try:
            minutes = int(time_str.split("in ")[1].split(" ")[0])
            return now + timedelta(minutes=minutes)
        except:
            pass

    # "in X hours"
    if "in " in time_str and "hour" in time_str:
        try:
            hours = int(time_str.split("in ")[1].split(" ")[0])
            return now + timedelta(hours=hours)
        except:
            pass

    # "tomorrow at Xam/pm"
    if "tomorrow" in time_str:
        tomorrow = now + timedelta(days=1)
        if "at " in time_str:
            try:
                time_part = time_str.split("at ")[1].strip()
                hour = int(time_part.replace("am", "").replace("pm", "").replace(":", "").strip()[:2])
                if "pm" in time_part and hour != 12:
                    hour += 12
                if "am" in time_part and hour == 12:
                    hour = 0
                return tomorrow.replace(hour=hour, minute=0, second=0, microsecond=0)
            except:
                pass
        return tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)

    # "at Xam/pm" (today)
    if time_str.startswith("at "):
        try:
            time_part = time_str.replace("at ", "").strip()
            hour = int(time_part.replace("am", "").replace("pm", "").replace(":", "").strip()[:2])
            if "pm" in time_part and hour != 12:
                hour += 12
            if "am" in time_part and hour == 12:
                hour = 0
            result = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if result <= now:
                result += timedelta(days=1)
            return result
        except:
            pass

    # ISO format "2024-01-28 14:00"
    try:
        return tz.localize(datetime.strptime(time_str, "%Y-%m-%d %H:%M"))
    except:
        pass

    return None
