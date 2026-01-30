"""
Resource Cleanup Daemon for Kiyomi Bot.

Handles periodic cleanup of:
- Old daily memory files (>30 days)
- Swarm agent log files (>7 days)
- Old session state files
- Truncated cost logs (keep last 90 days)
- Temp files from image/voice processing

Runs daily at 3:00 AM or on-demand via /cleanup command.
"""

import asyncio
import logging
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

import pytz

from config import (
    BASE_DIR,
    MEMORY_DIR,
    LOGS_DIR,
    TIMEZONE,
)

logger = logging.getLogger("kiyomi.cleanup")

# Cleanup thresholds
MEMORY_RETENTION_DAYS = 30
SWARM_LOG_RETENTION_DAYS = 7
COST_LOG_RETENTION_DAYS = 90
TEMP_FILE_RETENTION_HOURS = 24

# Directories to clean
SWARM_LOGS_DIR = BASE_DIR / "swarm_logs"
TEMP_DIR = BASE_DIR / "temp"


def _age_in_days(filepath: Path) -> float:
    """Get the age of a file in days."""
    try:
        mtime = filepath.stat().st_mtime
        age = datetime.now().timestamp() - mtime
        return age / 86400  # Convert seconds to days
    except OSError:
        return 0


def cleanup_old_memory_files(dry_run: bool = False) -> List[str]:
    """Remove daily memory files older than MEMORY_RETENTION_DAYS.

    Keeps MEMORY.md (long-term) untouched.
    Only removes dated files like 2026-01-01.md.
    """
    removed = []
    if not MEMORY_DIR.exists():
        return removed

    for f in MEMORY_DIR.iterdir():
        if not f.suffix == ".md":
            continue
        # Only remove dated files (YYYY-MM-DD.md pattern)
        name = f.stem
        try:
            datetime.strptime(name, "%Y-%m-%d")
        except ValueError:
            continue  # Not a dated file, skip

        if _age_in_days(f) > MEMORY_RETENTION_DAYS:
            if not dry_run:
                f.unlink()
            removed.append(str(f.name))

    return removed


def cleanup_swarm_logs(dry_run: bool = False) -> List[str]:
    """Remove swarm agent logs older than SWARM_LOG_RETENTION_DAYS."""
    removed = []
    if not SWARM_LOGS_DIR.exists():
        return removed

    for f in SWARM_LOGS_DIR.iterdir():
        if _age_in_days(f) > SWARM_LOG_RETENTION_DAYS:
            if not dry_run:
                f.unlink()
            removed.append(str(f.name))

    return removed


def cleanup_temp_files(dry_run: bool = False) -> List[str]:
    """Remove temporary files (images, voice, screenshots) older than threshold."""
    removed = []
    if not TEMP_DIR.exists():
        return removed

    for f in TEMP_DIR.iterdir():
        if f.is_file():
            age_hours = _age_in_days(f) * 24
            if age_hours > TEMP_FILE_RETENTION_HOURS:
                if not dry_run:
                    f.unlink()
                removed.append(str(f.name))

    return removed


def truncate_cost_log(dry_run: bool = False) -> int:
    """Keep only the last COST_LOG_RETENTION_DAYS entries in cost_log.json."""
    cost_file = BASE_DIR / "cost_log.json"
    if not cost_file.exists():
        return 0

    try:
        data = json.loads(cost_file.read_text())
        if not isinstance(data, list):
            return 0

        original_count = len(data)
        cutoff = (datetime.now() - timedelta(days=COST_LOG_RETENTION_DAYS)).isoformat()

        # Keep entries newer than cutoff
        filtered = [
            entry for entry in data
            if entry.get("timestamp", entry.get("date", "")) >= cutoff
        ]

        removed_count = original_count - len(filtered)
        if removed_count > 0 and not dry_run:
            cost_file.write_text(json.dumps(filtered, indent=2))

        return removed_count
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to truncate cost log: {e}")
        return 0


def cleanup_empty_dirs() -> List[str]:
    """Remove empty subdirectories in logs and swarm_logs."""
    removed = []
    for parent in [LOGS_DIR, SWARM_LOGS_DIR]:
        if not parent.exists():
            continue
        for d in parent.iterdir():
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
                removed.append(str(d.name))
    return removed


def run_full_cleanup(dry_run: bool = False) -> Dict[str, any]:
    """Run all cleanup tasks and return summary."""
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    results = {
        "timestamp": now.isoformat(),
        "dry_run": dry_run,
        "memory_files_removed": cleanup_old_memory_files(dry_run),
        "swarm_logs_removed": cleanup_swarm_logs(dry_run),
        "temp_files_removed": cleanup_temp_files(dry_run),
        "cost_entries_trimmed": truncate_cost_log(dry_run),
        "empty_dirs_removed": cleanup_empty_dirs() if not dry_run else [],
    }

    total = (
        len(results["memory_files_removed"])
        + len(results["swarm_logs_removed"])
        + len(results["temp_files_removed"])
        + results["cost_entries_trimmed"]
        + len(results["empty_dirs_removed"])
    )
    results["total_items_cleaned"] = total

    if total > 0:
        logger.info(f"Cleanup complete: {total} items removed (dry_run={dry_run})")
    else:
        logger.info("Cleanup complete: nothing to clean")

    return results


def format_cleanup_report(results: Dict) -> str:
    """Format cleanup results as a readable message."""
    lines = ["**Cleanup Report**\n"]

    if results["dry_run"]:
        lines.append("_(Dry run - no files were actually deleted)_\n")

    mem = results["memory_files_removed"]
    if mem:
        lines.append(f"Memory files (>{MEMORY_RETENTION_DAYS}d): {len(mem)} removed")

    swarm = results["swarm_logs_removed"]
    if swarm:
        lines.append(f"Swarm logs (>{SWARM_LOG_RETENTION_DAYS}d): {len(swarm)} removed")

    temp = results["temp_files_removed"]
    if temp:
        lines.append(f"Temp files (>{TEMP_FILE_RETENTION_HOURS}h): {len(temp)} removed")

    cost = results["cost_entries_trimmed"]
    if cost:
        lines.append(f"Cost log entries (>{COST_LOG_RETENTION_DAYS}d): {cost} trimmed")

    dirs = results["empty_dirs_removed"]
    if dirs:
        lines.append(f"Empty directories: {len(dirs)} removed")

    if results["total_items_cleaned"] == 0:
        lines.append("Everything is clean.")

    return "\n".join(lines)


async def scheduled_cleanup():
    """Run cleanup on schedule (called from heartbeat or scheduler)."""
    try:
        results = run_full_cleanup(dry_run=False)
        if results["total_items_cleaned"] > 0:
            logger.info(format_cleanup_report(results))
    except Exception as e:
        logger.error(f"Scheduled cleanup failed: {e}")
