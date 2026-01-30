"""
Kiyomi Watchdog - Ensure 24/7 reliability

Features:
- Health monitoring
- Auto-recovery from crashes
- Connection retry logic
- Memory management
- Log rotation
- Crash reporting
"""
import asyncio
import logging
import os
import signal
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Callable
import psutil

import pytz
from config import BASE_DIR, TIMEZONE, LOGS_DIR

logger = logging.getLogger(__name__)

# Watchdog configuration
HEALTH_CHECK_INTERVAL = 60  # seconds
MAX_MEMORY_MB = 500  # Restart if memory exceeds this
MAX_LOG_SIZE_MB = 50  # Rotate logs if they exceed this
CRASH_REPORT_FILE = BASE_DIR / "crash_reports.log"
HEALTH_FILE = BASE_DIR / "health.json"


class KiyomiWatchdog:
    """
    Watchdog to ensure Kiyomi stays healthy and running.
    """

    def __init__(self):
        self.start_time: Optional[datetime] = None
        self.last_health_check: Optional[datetime] = None
        self.restart_count: int = 0
        self.last_activity: Optional[datetime] = None
        self.is_healthy: bool = True
        self._shutdown_requested: bool = False

    def start(self) -> None:
        """Initialize the watchdog."""
        tz = pytz.timezone(TIMEZONE)
        self.start_time = datetime.now(tz)
        self.last_health_check = self.start_time
        self.last_activity = self.start_time

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

        logger.info("Watchdog started")

    def _handle_shutdown(self, signum, frame) -> None:
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown")
        self._shutdown_requested = True

    def record_activity(self) -> None:
        """Record that activity occurred (prevents false idle detection)."""
        tz = pytz.timezone(TIMEZONE)
        self.last_activity = datetime.now(tz)

    def check_health(self) -> dict:
        """
        Perform a health check.
        Returns dict with health status and metrics.
        """
        tz = pytz.timezone(TIMEZONE)
        now = datetime.now(tz)
        self.last_health_check = now

        health = {
            "timestamp": now.isoformat(),
            "healthy": True,
            "issues": [],
            "metrics": {}
        }

        # Check memory usage
        try:
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / 1024 / 1024
            health["metrics"]["memory_mb"] = round(memory_mb, 2)

            if memory_mb > MAX_MEMORY_MB:
                health["issues"].append(f"High memory usage: {memory_mb:.0f}MB")
                health["healthy"] = False
        except Exception as e:
            health["issues"].append(f"Could not check memory: {e}")

        # Check CPU usage
        try:
            cpu_percent = psutil.Process(os.getpid()).cpu_percent(interval=0.1)
            health["metrics"]["cpu_percent"] = cpu_percent
        except:
            pass

        # Check uptime
        if self.start_time:
            uptime = now - self.start_time
            health["metrics"]["uptime_hours"] = round(uptime.total_seconds() / 3600, 2)

        # Check log file sizes
        try:
            log_file = LOGS_DIR / "bot.log"
            if log_file.exists():
                log_size_mb = log_file.stat().st_size / 1024 / 1024
                health["metrics"]["log_size_mb"] = round(log_size_mb, 2)

                if log_size_mb > MAX_LOG_SIZE_MB:
                    health["issues"].append(f"Log file large: {log_size_mb:.0f}MB")
                    self._rotate_logs()
        except:
            pass

        # Check last activity
        if self.last_activity:
            idle_minutes = (now - self.last_activity).total_seconds() / 60
            health["metrics"]["idle_minutes"] = round(idle_minutes, 1)

        self.is_healthy = health["healthy"]

        # Write health to file
        self._write_health_file(health)

        return health

    def _write_health_file(self, health: dict) -> None:
        """Write health status to file for external monitoring."""
        import json
        try:
            with open(HEALTH_FILE, "w") as f:
                json.dump(health, f, indent=2)
        except:
            pass

    def _rotate_logs(self) -> None:
        """Rotate log files to prevent disk fill."""
        try:
            tz = pytz.timezone(TIMEZONE)
            timestamp = datetime.now(tz).strftime("%Y%m%d_%H%M%S")

            log_file = LOGS_DIR / "bot.log"
            if log_file.exists():
                archive_name = LOGS_DIR / f"bot_{timestamp}.log"
                log_file.rename(archive_name)
                logger.info(f"Rotated log to {archive_name}")

                # Keep only last 5 archived logs
                archives = sorted(LOGS_DIR.glob("bot_*.log"))
                for old_archive in archives[:-5]:
                    old_archive.unlink()

        except Exception as e:
            logger.error(f"Log rotation failed: {e}")

    def report_crash(self, error: Exception) -> None:
        """Log a crash for analysis."""
        tz = pytz.timezone(TIMEZONE)
        timestamp = datetime.now(tz).isoformat()

        crash_info = f"""
================================================================================
CRASH REPORT - {timestamp}
================================================================================
Error Type: {type(error).__name__}
Error Message: {str(error)}

Traceback:
{traceback.format_exc()}

Metrics at crash:
- Uptime: {(datetime.now(tz) - self.start_time).total_seconds() / 3600:.2f} hours
- Restart count: {self.restart_count}
================================================================================
"""

        try:
            with open(CRASH_REPORT_FILE, "a") as f:
                f.write(crash_info)
            logger.error(f"Crash reported: {error}")
        except:
            pass

    def should_restart(self) -> bool:
        """Determine if Kiyomi should be restarted."""
        if self._shutdown_requested:
            return False

        if not self.is_healthy:
            return True

        return False


# Global watchdog instance
_watchdog: Optional[KiyomiWatchdog] = None


def get_watchdog() -> KiyomiWatchdog:
    """Get or create the global watchdog instance."""
    global _watchdog
    if _watchdog is None:
        _watchdog = KiyomiWatchdog()
    return _watchdog


async def start_health_monitor(send_callback: Optional[Callable] = None) -> None:
    """
    Start the background health monitoring loop.
    """
    watchdog = get_watchdog()
    watchdog.start()

    while True:
        try:
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

            health = watchdog.check_health()

            if not health["healthy"]:
                logger.warning(f"Health check failed: {health['issues']}")

                if send_callback:
                    issues = "\n".join(f"• {i}" for i in health["issues"])
                    await send_callback(
                        f"⚠️ **Kiyomi Health Warning**\n\n{issues}\n\n"
                        f"_Auto-recovery in progress..._"
                    )

                # Attempt recovery
                if watchdog.should_restart():
                    logger.info("Watchdog requesting restart")
                    # Let launchd handle the restart
                    sys.exit(1)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Health monitor error: {e}")


def record_activity() -> None:
    """Record activity (call this on each user interaction)."""
    watchdog = get_watchdog()
    watchdog.record_activity()


def report_crash(error: Exception) -> None:
    """Report a crash."""
    watchdog = get_watchdog()
    watchdog.report_crash(error)


def get_health_status() -> dict:
    """Get current health status."""
    watchdog = get_watchdog()
    return watchdog.check_health()


def get_uptime() -> str:
    """Get formatted uptime string."""
    watchdog = get_watchdog()
    if watchdog.start_time:
        tz = pytz.timezone(TIMEZONE)
        delta = datetime.now(tz) - watchdog.start_time
        hours = int(delta.total_seconds() // 3600)
        minutes = int((delta.total_seconds() % 3600) // 60)
        return f"{hours}h {minutes}m"
    return "Unknown"
