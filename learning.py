"""
Kiyomi Learning System - Continuous background learning and self-improvement

Kiyomi should never be idle. When not responding to Richard, she should:
1. Review her memory files
2. Read her skill files
3. Review conversation history
4. Update her understanding
5. Prepare for upcoming tasks
"""
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Callable
import pytz
import json

from config import TIMEZONE, BASE_DIR, WORKSPACE_DIR, MEMORY_DIR

logger = logging.getLogger(__name__)

# Paths to learn from
SKILLS_DIR = Path("/Users/richardecholsai2/kiyomi/skills")
CONVERSATION_HISTORY_FILE = BASE_DIR / "conversation_history.json"

# Learning state
_is_learning = False
_last_learning_time: Optional[datetime] = None
_learning_summary: str = ""

# Learning intervals
LEARNING_INTERVAL_MINUTES = 10  # Review context every 10 minutes
DEEP_LEARNING_INTERVAL_MINUTES = 60  # Deep review every hour


async def start_learning_loop(notify_callback: Optional[Callable] = None) -> None:
    """
    Start the continuous learning loop.

    Args:
        notify_callback: Optional async function to notify Richard of insights
    """
    global _is_learning, _last_learning_time

    logger.info("Starting Kiyomi learning loop...")

    learning_cycle = 0

    while True:
        try:
            _is_learning = True
            learning_cycle += 1

            # Quick review every cycle
            await _quick_context_refresh()

            # Deep learning every 6th cycle (hourly)
            if learning_cycle % 6 == 0:
                insights = await _deep_learning_session()
                if insights and notify_callback:
                    # Only notify during non-quiet hours
                    tz = pytz.timezone(TIMEZONE)
                    hour = datetime.now(tz).hour
                    if 8 <= hour <= 22:  # 8 AM to 10 PM
                        await notify_callback(f"🧠 Learning insight: {insights}")

            _last_learning_time = datetime.now(pytz.timezone(TIMEZONE))
            _is_learning = False

        except Exception as e:
            logger.error(f"Learning loop error: {e}")
            _is_learning = False

        # Wait for next learning cycle
        await asyncio.sleep(LEARNING_INTERVAL_MINUTES * 60)


async def _quick_context_refresh() -> None:
    """Quick refresh of essential context - runs every 10 minutes."""
    logger.debug("Quick context refresh...")

    try:
        # Read and cache key files
        files_to_refresh = [
            WORKSPACE_DIR / "COMMITMENTS.md",
            WORKSPACE_DIR / "MEMORY.md",
            WORKSPACE_DIR / "ACTIVE_PROJECT.md",
        ]

        for file_path in files_to_refresh:
            if file_path.exists():
                content = file_path.read_text()
                # Just reading refreshes the file system cache
                # In future: could parse and index for quick retrieval

        # Check conversation history for patterns
        if CONVERSATION_HISTORY_FILE.exists():
            with open(CONVERSATION_HISTORY_FILE, "r") as f:
                history = json.load(f)

            # Count recent messages
            recent_count = len(history)
            if recent_count > 0:
                logger.debug(f"Conversation history: {recent_count} messages")

    except Exception as e:
        logger.warning(f"Quick refresh error: {e}")


async def _deep_learning_session() -> Optional[str]:
    """
    Deep learning session - review skills, find patterns, generate insights.
    Runs every hour.

    Returns:
        Optional insight string to share with Richard
    """
    logger.info("Starting deep learning session...")

    insights = []

    try:
        # 1. Review skill files
        skill_files = list(SKILLS_DIR.glob("*.md"))
        logger.info(f"Reviewing {len(skill_files)} skill files...")

        # 2. Review recent conversation patterns
        if CONVERSATION_HISTORY_FILE.exists():
            with open(CONVERSATION_HISTORY_FILE, "r") as f:
                history = json.load(f)

            # Find frequently mentioned topics
            if len(history) > 10:
                all_text = " ".join(msg.get("content", "") for msg in history[-50:])

                # Simple keyword analysis
                keywords = ["deploy", "bug", "fix", "build", "test", "vercel", "supabase"]
                mentioned = [k for k in keywords if k.lower() in all_text.lower()]

                if mentioned:
                    insights.append(f"Recent focus: {', '.join(mentioned)}")

        # 3. Check for pending commitments
        commitments_file = WORKSPACE_DIR / "COMMITMENTS.md"
        if commitments_file.exists():
            content = commitments_file.read_text()

            # Look for unchecked items
            unchecked = content.count("- [ ]")
            if unchecked > 0:
                insights.append(f"{unchecked} pending commitments")

        # 4. Check active project status
        active_project = WORKSPACE_DIR / "ACTIVE_PROJECT.md"
        if active_project.exists():
            content = active_project.read_text()
            if "INCOMPLETE" in content or "in progress" in content.lower():
                # Extract project name
                lines = content.split("\n")
                for line in lines:
                    if "**Name:**" in line:
                        project_name = line.split("**Name:**")[1].strip()
                        insights.append(f"Active project: {project_name}")
                        break

        # 5. Review today's memory
        tz = pytz.timezone(TIMEZONE)
        today = datetime.now(tz).strftime("%Y-%m-%d")
        today_memory = MEMORY_DIR / f"{today}.md"
        if today_memory.exists():
            content = today_memory.read_text()
            entry_count = content.count("### ")
            if entry_count > 0:
                insights.append(f"{entry_count} activities logged today")

        logger.info(f"Deep learning complete. Insights: {insights}")

        if insights:
            return " | ".join(insights)
        return None

    except Exception as e:
        logger.error(f"Deep learning error: {e}")
        return None


def get_learning_status() -> dict:
    """Get current learning status."""
    return {
        "is_learning": _is_learning,
        "last_learning": _last_learning_time.isoformat() if _last_learning_time else None,
        "summary": _learning_summary
    }


async def force_learning_cycle() -> str:
    """Force an immediate learning cycle."""
    await _quick_context_refresh()
    insights = await _deep_learning_session()
    return insights or "No new insights"
