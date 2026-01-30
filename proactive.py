"""
Kiyomi Proactive System - Autonomous behaviors like Brock

This module handles:
1. 8:00 AM Silent Prep
2. End-of-session auto-summary
3. "Keep the factory running" overnight mode
4. Email checking
5. Calendar checking
6. Natural language command parsing
7. Web search
8. TTS (ElevenLabs)
"""
import asyncio
import logging
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Callable, Dict, List, Tuple
import pytz

from config import TIMEZONE, BASE_DIR, WORKSPACE_DIR, MEMORY_DIR

logger = logging.getLogger(__name__)

# State tracking
_last_richard_message: Optional[datetime] = None
_factory_mode: bool = False
_session_active: bool = False
_silent_prep_done_today: Optional[str] = None

# Thresholds
IDLE_THRESHOLD_MINUTES = 30  # Consider session ended after 30 min idle
PREP_HOUR = 8  # 8:00 AM silent prep
PREP_MINUTE = 0


def update_last_richard_message():
    """Track when Richard last sent a message."""
    global _last_richard_message, _session_active
    _last_richard_message = datetime.now(pytz.timezone(TIMEZONE))
    _session_active = True


def is_session_idle() -> bool:
    """Check if Richard has been idle for a while."""
    if _last_richard_message is None:
        return True

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    idle_time = (now - _last_richard_message).total_seconds() / 60

    return idle_time > IDLE_THRESHOLD_MINUTES


def is_factory_mode() -> bool:
    """Check if factory mode is active."""
    return _factory_mode


def enable_factory_mode():
    """Enable overnight autonomous mode."""
    global _factory_mode
    _factory_mode = True
    logger.info("Factory mode enabled - running autonomously")


def disable_factory_mode():
    """Disable factory mode."""
    global _factory_mode
    _factory_mode = False
    logger.info("Factory mode disabled")


# ============================================
# NATURAL LANGUAGE COMMAND PARSING
# ============================================

def parse_natural_command(text: str) -> Optional[Tuple[str, str]]:
    """
    Parse natural language commands like Brock does.

    Returns:
        Tuple of (command_type, argument) or None
    """
    text_lower = text.lower().strip()

    # "Remember this: <content>" or "Remember that <content>"
    remember_patterns = [
        r"remember this[:\s]+(.+)",
        r"remember that[:\s]+(.+)",
        r"note this[:\s]+(.+)",
        r"save this[:\s]+(.+)",
    ]
    for pattern in remember_patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE | re.DOTALL)
        if match:
            return ("remember", match.group(1).strip())

    # "Add to tomorrow's agenda: <item>"
    agenda_patterns = [
        r"add to (?:tomorrow'?s? )?agenda[:\s]+(.+)",
        r"add (?:this )?to (?:the )?agenda[:\s]+(.+)",
        # r"tomorrow[:\s]+(.+)",  # TOO AGGRESSIVE - catches normal conversation
        r"agenda[:\s]+(.+)",
    ]
    for pattern in agenda_patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE | re.DOTALL)
        if match:
            return ("agenda", match.group(1).strip())

    # "Spawn an agent to <task>"
    spawn_patterns = [
        r"spawn (?:an? )?agent (?:to )?(.+)",
        r"background[:\s]+(.+)",
        r"run in background[:\s]+(.+)",
    ]
    for pattern in spawn_patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE | re.DOTALL)
        if match:
            return ("spawn", match.group(1).strip())

    # "Keep the factory running"
    if any(phrase in text_lower for phrase in [
        "keep the factory running",
        "factory mode",
        "run overnight",
        "work overnight",
        "autonomous mode"
    ]):
        return ("factory", "")

    # "What's on the agenda?" / "Status report"
    if any(phrase in text_lower for phrase in [
        "what's on the agenda",
        "whats on the agenda",
        "show agenda",
        "today's agenda",
        "todays agenda"
    ]):
        return ("show_agenda", "")

    if any(phrase in text_lower for phrase in [
        "status report",
        "give me a status",
        "what's the status",
        "whats the status"
    ]):
        return ("status", "")

    return None


async def execute_natural_command(
    command_type: str,
    argument: str,
    send_callback: Callable
) -> bool:
    """
    Execute a parsed natural language command.

    Returns:
        True if command was handled, False otherwise
    """
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    if command_type == "remember":
        # Write to memory files
        try:
            # Add to today's memory
            today = now.strftime("%Y-%m-%d")
            daily_file = MEMORY_DIR / f"{today}.md"

            entry = f"\n### {now.strftime('%H:%M')} - Remembered\n{argument}\n"

            with open(daily_file, "a") as f:
                f.write(entry)

            # Also add to MEMORY.md if it seems important
            if len(argument) > 50:  # Longer items go to long-term memory
                memory_file = WORKSPACE_DIR / "MEMORY.md"
                with open(memory_file, "a") as f:
                    f.write(f"\n\n## Noted ({today})\n{argument}\n")

            await send_callback(f"🌸 ✅ Remembered: {argument[:100]}{'...' if len(argument) > 100 else ''}")
            return True

        except Exception as e:
            logger.error(f"Error saving to memory: {e}")
            await send_callback(f"🌸 ❌ Failed to save to memory: {str(e)[:50]}")
            return True

    elif command_type == "agenda":
        # Add to COMMITMENTS.md
        try:
            commitments_file = WORKSPACE_DIR / "COMMITMENTS.md"
            content = commitments_file.read_text()

            # Find "## Today's Agenda" section and add item
            if "## Today's Agenda" in content:
                content = content.replace(
                    "## Today's Agenda\n",
                    f"## Today's Agenda\n\n- [ ] {argument}\n"
                )
            elif "## Pending Items" in content:
                content = content.replace(
                    "## Pending Items\n",
                    f"## Pending Items\n\n- [ ] {argument}\n"
                )
            else:
                content += f"\n\n## Today's Agenda\n\n- [ ] {argument}\n"

            commitments_file.write_text(content)
            await send_callback(f"🌸 ✅ Added to agenda: {argument}")
            return True

        except Exception as e:
            logger.error(f"Error adding to agenda: {e}")
            await send_callback(f"🌸 ❌ Failed to add to agenda: {str(e)[:50]}")
            return True

    elif command_type == "spawn":
        # This will be handled by the main bot - return False to pass through
        return False

    elif command_type == "factory":
        enable_factory_mode()
        await send_callback(
            "🌸 🏭 **Factory mode activated**\n\n"
            "I'll keep working through the night:\n"
            "• Executing tasks in HEARTBEAT.md\n"
            "• Spawning agents for long work\n"
            "• Reporting results in morning brief\n\n"
            "Sleep well, Richard. I've got this."
        )
        return True

    elif command_type == "show_agenda":
        try:
            commitments_file = WORKSPACE_DIR / "COMMITMENTS.md"
            content = commitments_file.read_text()

            # Extract agenda section
            agenda = ""
            in_agenda = False
            for line in content.split("\n"):
                if "## Today's Agenda" in line or "## Pending Items" in line:
                    in_agenda = True
                    agenda += line + "\n"
                elif in_agenda and line.startswith("## "):
                    break
                elif in_agenda:
                    agenda += line + "\n"

            if agenda.strip():
                await send_callback(f"🌸 📋 **Agenda**\n\n{agenda}")
            else:
                await send_callback("🌸 📋 No items on the agenda right now.")
            return True

        except Exception as e:
            await send_callback(f"🌸 ❌ Couldn't read agenda: {str(e)[:50]}")
            return True

    elif command_type == "status":
        # Generate status report
        try:
            status_parts = ["🌸 **Status Report**\n"]

            # Active project
            active_project = WORKSPACE_DIR / "ACTIVE_PROJECT.md"
            if active_project.exists():
                content = active_project.read_text()
                for line in content.split("\n"):
                    if "**Name:**" in line:
                        status_parts.append(f"📁 **Project:** {line.split('**Name:**')[1].strip()}")
                        break
                    if "**Status:**" in line:
                        status_parts.append(f"📊 {line}")

            # Pending tasks
            heartbeat = WORKSPACE_DIR / "HEARTBEAT.md"
            if heartbeat.exists():
                content = heartbeat.read_text()
                pending = content.count("- [ ]")
                if pending > 0:
                    status_parts.append(f"⏳ **Pending tasks:** {pending}")

            # Factory mode
            if _factory_mode:
                status_parts.append("🏭 **Factory mode:** Active")

            # Session status
            if _last_richard_message:
                idle_mins = int((datetime.now(tz) - _last_richard_message).total_seconds() / 60)
                status_parts.append(f"💬 **Last message:** {idle_mins} min ago")

            await send_callback("\n".join(status_parts))
            return True

        except Exception as e:
            await send_callback(f"🌸 ❌ Status error: {str(e)[:50]}")
            return True

    return False


# ============================================
# 8:00 AM SILENT PREP
# ============================================

async def do_silent_prep() -> Dict:
    """
    8:00 AM silent preparation.
    Read all files and prepare for the day without messaging Richard.

    Returns:
        Dict with prep results
    """
    global _silent_prep_done_today

    tz = pytz.timezone(TIMEZONE)
    today = tz.localize(datetime.now()).strftime("%Y-%m-%d")

    if _silent_prep_done_today == today:
        return {"status": "already_done"}

    logger.info("Starting 8:00 AM silent prep...")

    results = {
        "status": "completed",
        "files_read": [],
        "pending_tasks": 0,
        "commitments": [],
    }

    try:
        # Read all workspace files
        workspace_files = [
            "IDENTITY.md", "SOUL.md", "USER.md", "MEMORY.md",
            "COMMITMENTS.md", "HEARTBEAT.md", "AGENTS.md", "TOOLS.md",
            "ACTIVE_PROJECT.md", "SESSION_LOG.md"
        ]

        for filename in workspace_files:
            filepath = WORKSPACE_DIR / filename
            if filepath.exists():
                content = filepath.read_text()
                results["files_read"].append(filename)

                # Extract specific info
                if filename == "HEARTBEAT.md":
                    results["pending_tasks"] = content.count("- [ ]")

                if filename == "COMMITMENTS.md":
                    # Extract today's commitments
                    for line in content.split("\n"):
                        if line.strip().startswith("- [ ]"):
                            results["commitments"].append(line.strip()[5:].strip())

        # Read memory files
        daily_memory = MEMORY_DIR / f"{today}.md"
        yesterday = (datetime.now(tz) - timedelta(days=1)).strftime("%Y-%m-%d")
        yesterday_memory = MEMORY_DIR / f"{yesterday}.md"

        for mem_file in [daily_memory, yesterday_memory]:
            if mem_file.exists():
                results["files_read"].append(str(mem_file.name))

        # Read skill files (just list them for context)
        skills_dir = Path("/Users/richardecholsai2/kiyomi/skills")
        if skills_dir.exists():
            results["skills_available"] = len(list(skills_dir.glob("*.md")))

        _silent_prep_done_today = today
        logger.info(f"Silent prep completed: {len(results['files_read'])} files read")

    except Exception as e:
        logger.error(f"Silent prep error: {e}")
        results["status"] = "error"
        results["error"] = str(e)

    return results


def is_prep_time() -> bool:
    """Check if it's 8:00 AM prep time."""
    global _silent_prep_done_today

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    today = now.strftime("%Y-%m-%d")

    # Already done today?
    if _silent_prep_done_today == today:
        return False

    # Is it 8:00-8:30 AM?
    if now.hour == PREP_HOUR and now.minute < 30:
        return True

    return False


# ============================================
# END OF SESSION SUMMARY
# ============================================

async def do_session_summary(send_callback: Optional[Callable] = None) -> str:
    """
    Generate end-of-session summary when Richard goes idle.

    Returns:
        Summary text
    """
    global _session_active

    if not _session_active:
        return "No active session to summarize"

    logger.info("Generating end-of-session summary...")

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    today = now.strftime("%Y-%m-%d")

    summary_parts = []

    try:
        # Read today's session log
        session_log = WORKSPACE_DIR / "SESSION_LOG.md"
        if session_log.exists():
            content = session_log.read_text()

            # Count today's entries
            today_entries = content.count(f"## {today}")
            summary_parts.append(f"**Tasks completed today:** {today_entries}")

        # Read conversation history for key topics
        conv_history = BASE_DIR / "conversation_history.json"
        if conv_history.exists():
            with open(conv_history, "r") as f:
                history = json.load(f)

            # Get today's messages
            today_messages = [m for m in history if m.get("timestamp", "").startswith(today)]

            if today_messages:
                summary_parts.append(f"**Messages exchanged:** {len(today_messages)}")

                # Extract key topics (simple keyword extraction)
                all_text = " ".join(m.get("content", "") for m in today_messages[-20:])
                keywords = ["deploy", "build", "fix", "test", "podcast", "app", "vercel", "supabase"]
                mentioned = [k for k in keywords if k.lower() in all_text.lower()]
                if mentioned:
                    summary_parts.append(f"**Topics:** {', '.join(mentioned)}")

        # Check for incomplete tasks
        heartbeat = WORKSPACE_DIR / "HEARTBEAT.md"
        if heartbeat.exists():
            content = heartbeat.read_text()
            pending = content.count("- [ ]")
            if pending > 0:
                summary_parts.append(f"**Pending tasks:** {pending}")

        # Write summary to daily memory
        if summary_parts:
            summary_text = "\n".join(summary_parts)
            daily_file = MEMORY_DIR / f"{today}.md"

            entry = f"\n\n### {now.strftime('%H:%M')} - Session Summary\n{summary_text}\n"
            with open(daily_file, "a") as f:
                f.write(entry)

            _session_active = False

            if send_callback:
                await send_callback(f"🌸 📝 **Session wrapped up**\n\n{summary_text}\n\nI'll keep an eye on things.")

            return summary_text

    except Exception as e:
        logger.error(f"Session summary error: {e}")
        return f"Error generating summary: {str(e)}"

    _session_active = False
    return "Session ended - nothing significant to report"


# ============================================
# PROACTIVE CHECK ROTATION
# ============================================

_check_index = 0
_check_rotation = ["heartbeat", "commitments", "project", "weather"]


async def do_rotation_check(send_callback: Callable) -> Optional[str]:
    """
    Rotate through different proactive checks.
    Called during heartbeat.

    Returns:
        Message to send if something noteworthy, None otherwise
    """
    global _check_index

    check_type = _check_rotation[_check_index % len(_check_rotation)]
    _check_index += 1

    logger.debug(f"Rotation check: {check_type}")

    try:
        if check_type == "heartbeat":
            # Heartbeat urgent task notifications disabled - too noisy
            pass

        elif check_type == "commitments":
            # Check for overdue commitments
            pass  # Handled by reminders system

        elif check_type == "project":
            # Check active project status
            pass  # Handled by reminders system

        elif check_type == "weather":
            # Weather check would go here
            # For now, skip - would need API integration
            pass

    except Exception as e:
        logger.error(f"Rotation check error ({check_type}): {e}")

    return None


# ============================================
# OVERNIGHT FACTORY MODE
# ============================================

async def run_factory_mode(
    execute_callback: Callable,
    send_callback: Callable
) -> List[str]:
    """
    Run overnight factory mode - execute all pending tasks.

    Args:
        execute_callback: Function to execute tasks
        send_callback: Function to send messages

    Returns:
        List of completed task descriptions
    """
    if not _factory_mode:
        return []

    logger.info("Running factory mode tasks...")
    completed = []

    try:
        # Read HEARTBEAT.md for pending tasks
        heartbeat = WORKSPACE_DIR / "HEARTBEAT.md"
        if not heartbeat.exists():
            return []

        content = heartbeat.read_text()

        # Extract uncompleted tasks
        tasks = []
        for line in content.split("\n"):
            if line.strip().startswith("- [ ]"):
                task = line.strip()[5:].strip()
                if task:
                    tasks.append(task)

        if not tasks:
            logger.info("Factory mode: No pending tasks")
            return []

        logger.info(f"Factory mode: Found {len(tasks)} pending tasks")

        # Execute tasks (limit to prevent runaway)
        max_tasks = 5
        for task in tasks[:max_tasks]:
            try:
                logger.info(f"Factory mode executing: {task[:50]}...")
                result, success = await execute_callback(task)

                if success:
                    completed.append(task)

                    # Mark as completed in HEARTBEAT.md
                    content = content.replace(f"- [ ] {task}", f"- [x] {task}")
                    heartbeat.write_text(content)

                # Small delay between tasks
                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Factory mode task error: {e}")

    except Exception as e:
        logger.error(f"Factory mode error: {e}")

    return completed
