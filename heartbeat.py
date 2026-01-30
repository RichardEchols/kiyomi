"""
Kiyomi Heartbeat System - Scheduled task execution
"""
import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pytz

from config import (
    TIMEZONE, HEARTBEAT_INTERVAL_MINUTES,
    MORNING_BRIEF_HOUR, MORNING_BRIEF_MINUTE,
    QUIET_HOURS_START, QUIET_HOURS_END,
    BOT_EMOJI, BOT_NAME
)
from memory_manager import (
    read_heartbeat, update_heartbeat, log_to_today,
    get_today_date
)
from executor import execute_claude
from proactive import (
    is_prep_time, do_silent_prep, is_session_idle,
    do_session_summary, is_factory_mode, run_factory_mode,
    do_rotation_check
)

logger = logging.getLogger(__name__)

# Track last message time from Richard
_last_richard_message_time: Optional[datetime] = None
_last_heartbeat_time: Optional[datetime] = None


def update_last_message_time():
    """Update the last time Richard sent a message."""
    global _last_richard_message_time
    _last_richard_message_time = datetime.now(pytz.timezone(TIMEZONE))


def is_richard_active(minutes: int = 5) -> bool:
    """Check if Richard sent a message recently."""
    if _last_richard_message_time is None:
        return False

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    threshold = now - timedelta(minutes=minutes)
    return _last_richard_message_time > threshold


def is_quiet_hours() -> bool:
    """Check if it's during quiet hours (night time)."""
    tz = pytz.timezone(TIMEZONE)
    current_hour = datetime.now(tz).hour

    if QUIET_HOURS_START > QUIET_HOURS_END:
        # Quiet hours span midnight (e.g., 23:00 to 08:00)
        return current_hour >= QUIET_HOURS_START or current_hour < QUIET_HOURS_END
    else:
        return QUIET_HOURS_START <= current_hour < QUIET_HOURS_END


# Persist morning brief state to survive restarts
from pathlib import Path
MORNING_BRIEF_STATE_FILE = Path(__file__).parent / "workspace" / ".morning_brief_date"

def _get_morning_brief_sent_date() -> Optional[str]:
    """Get the date of last morning brief from file."""
    try:
        if MORNING_BRIEF_STATE_FILE.exists():
            return MORNING_BRIEF_STATE_FILE.read_text().strip()
    except:
        pass
    return None

def is_morning_brief_time() -> bool:
    """Check if it's time for the morning brief.

    Returns True if:
    - It's between 8:30 AM and 9:30 AM (buffer for missed windows)
    - We haven't sent a brief today yet
    """
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    today = now.strftime("%Y-%m-%d")

    # Already sent today?
    if _get_morning_brief_sent_date() == today:
        return False

    # Check if we're in the morning brief window (8:30-9:30)
    if now.hour == MORNING_BRIEF_HOUR and now.minute >= MORNING_BRIEF_MINUTE:
        return True
    if now.hour == MORNING_BRIEF_HOUR + 1 and now.minute < 30:
        return True

    return False


def mark_morning_brief_sent():
    """Mark that we've sent the morning brief today (persisted to file).

    Uses atomic write (write to temp file, then rename) to prevent
    race conditions if multiple processes check/write simultaneously.
    """
    try:
        tz = pytz.timezone(TIMEZONE)
        today = datetime.now(tz).strftime("%Y-%m-%d")
        # Atomic write: write to temp file then rename
        tmp_file = MORNING_BRIEF_STATE_FILE.with_suffix(".tmp")
        tmp_file.write_text(today)
        tmp_file.rename(MORNING_BRIEF_STATE_FILE)
    except Exception as e:
        logger.error(f"Failed to save morning brief state: {e}")


def parse_heartbeat_tasks(content: str) -> List[Dict]:
    """Parse HEARTBEAT.md to extract pending tasks."""
    tasks = []
    if not content:
        return tasks

    # Find pending tasks section
    pending_section = re.search(
        r'##\s*Pending\s*Tasks\s*\n(.*?)(?=\n##|$)',
        content,
        re.DOTALL | re.IGNORECASE
    )

    if not pending_section:
        return tasks

    # Extract uncompleted tasks (lines starting with - [ ])
    task_pattern = re.compile(r'-\s*\[\s*\]\s*(.+)')
    for match in task_pattern.finditer(pending_section.group(1)):
        tasks.append({
            "description": match.group(1).strip(),
            "completed": False
        })

    return tasks


def mark_task_completed(content: str, task_description: str) -> str:
    """Mark a task as completed in the heartbeat content."""
    # Replace the uncompleted task with completed version
    pattern = re.escape(f"- [ ] {task_description}")
    replacement = f"- [x] {task_description}"
    return re.sub(pattern, replacement, content)


async def run_heartbeat(send_message_callback) -> None:
    """
    Run a heartbeat check.

    Args:
        send_message_callback: Async function to send Telegram messages
    """
    global _last_heartbeat_time

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    logger.info(f"Heartbeat running at {now.strftime('%H:%M')}")

    # 1. Check for 8:00 AM silent prep time
    if is_prep_time():
        logger.info("Running 8:00 AM silent prep...")
        prep_result = await do_silent_prep()
        if prep_result["status"] == "completed":
            logger.info(f"Silent prep done: {len(prep_result.get('files_read', []))} files read")
            log_to_today(f"Silent prep completed - {prep_result.get('pending_tasks', 0)} pending tasks")
        # Don't return - continue to other checks

    # 2. Check for session idle summary
    if is_session_idle() and not is_quiet_hours():
        logger.info("Session idle - generating summary")
        await do_session_summary(send_message_callback)

    # 3. Skip regular heartbeat if Richard is actively chatting
    if is_richard_active(minutes=5):
        logger.info("Skipping heartbeat - Richard is active")
        return

    # 4. Check for morning brief time (mark BEFORE sending to prevent duplicates on restart)
    if is_morning_brief_time():
        mark_morning_brief_sent()  # Mark first to prevent race condition
        await send_morning_brief(send_message_callback)
        _last_heartbeat_time = now
        return

    # 5. Run factory mode if enabled (overnight autonomous work)
    if is_factory_mode() and is_quiet_hours():
        logger.info("Running factory mode tasks...")
        completed = await run_factory_mode(execute_claude, send_message_callback)
        if completed:
            log_to_today(f"Factory mode completed {len(completed)} tasks: {', '.join(completed[:3])}")
        _last_heartbeat_time = now
        return

    # 6. Skip detailed checks during quiet hours (unless factory mode)
    if is_quiet_hours():
        logger.info("Quiet hours - minimal heartbeat")
        return

    # 7. Run rotation check (commitments, weather, etc.)
    rotation_msg = await do_rotation_check(send_message_callback)
    if rotation_msg:
        await send_message_callback(rotation_msg)

    # 8. Read heartbeat file for pending tasks
    heartbeat_content = read_heartbeat()
    tasks = parse_heartbeat_tasks(heartbeat_content)

    if not tasks:
        logger.info("No pending tasks in heartbeat")
        _last_heartbeat_time = now
        return

    # Execute up to 2 pending tasks
    tasks_executed = 0
    for task in tasks[:2]:
        if task["completed"]:
            continue

        logger.info(f"Executing heartbeat task: {task['description'][:50]}...")

        try:
            result, success = await execute_claude(task["description"])

            if success:
                # Mark task as completed
                heartbeat_content = mark_task_completed(
                    heartbeat_content,
                    task["description"]
                )
                update_heartbeat(heartbeat_content)

                # Log to daily memory
                log_to_today(f"Heartbeat completed: {task['description'][:100]}")

                tasks_executed += 1
        except Exception as e:
            logger.error(f"Error executing heartbeat task: {e}")

    # Notify Richard if tasks were completed (outside quiet hours)
    if tasks_executed > 0 and not is_quiet_hours():
        # Log silently — don't spam Richard
        logger.info(f"Completed {tasks_executed} background task(s)")

    _last_heartbeat_time = now


async def send_morning_brief(send_message_callback) -> None:
    """Generate and send the morning brief."""
    logger.info("Generating morning brief...")

    brief_prompt = """
    Generate Richard's morning brief. Include:
    1. Daily Text from wol.jw.org (FULL TEXT - scripture + commentary)
    2. Weather for Atlanta
    3. Any overnight work summary
    4. ScribbleStokes video script idea
    5. @RichardBEchols vibe coding video idea
    6. App idea of the day
    7. US Politics (3 brief stories)
    8. World News (3 brief stories)
    9. AI & Tech news
    10. Tasks and priorities for the day (from COMMITMENTS.md)

    Format it nicely for Telegram. Keep each section concise.
    """

    try:
        result, success = await execute_claude(brief_prompt)

        if success:
            await send_message_callback(f"{BOT_EMOJI} Good morning, Richard!\n\n{result}")
            log_to_today("Morning brief sent")
        else:
            await send_message_callback(
                f"{BOT_EMOJI} Had trouble generating the morning brief: {result[:200]}"
            )
    except Exception as e:
        logger.error(f"Error sending morning brief: {e}")
        await send_message_callback(f"{BOT_EMOJI} Morning brief failed: {str(e)[:100]}")


async def start_heartbeat_scheduler(send_message_callback) -> None:
    """Start the heartbeat scheduler loop."""
    logger.info(f"Starting heartbeat scheduler (every {HEARTBEAT_INTERVAL_MINUTES} minutes)")

    while True:
        try:
            await run_heartbeat(send_message_callback)
        except Exception as e:
            logger.exception(f"Heartbeat error: {e}")

        # Wait for next heartbeat
        await asyncio.sleep(HEARTBEAT_INTERVAL_MINUTES * 60)
