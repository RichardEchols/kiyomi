"""
Kiyomi Monitoring - Proactive site health checks

This module provides:
- Periodic health checks for deployed sites
- Alert on downtime
- Response time tracking
"""
import asyncio
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
import pytz

from config import TIMEZONE
from projects import PROJECTS, Project, get_vercel_projects

logger = logging.getLogger(__name__)

# Check interval
CHECK_INTERVAL_MINUTES = 60  # Check every hour
ALERT_COOLDOWN_MINUTES = 30  # Don't alert again within 30 min

# Response time thresholds
SLOW_THRESHOLD_MS = 3000  # 3 seconds
TIMEOUT_SECONDS = 10


@dataclass
class SiteStatus:
    """Status of a monitored site."""
    url: str
    is_up: bool
    status_code: Optional[int] = None
    response_time_ms: Optional[int] = None
    last_check: Optional[datetime] = None
    last_alert: Optional[datetime] = None
    consecutive_failures: int = 0
    error_message: Optional[str] = None


# Track site statuses
_site_statuses: Dict[str, SiteStatus] = {}


def get_status(url: str) -> Optional[SiteStatus]:
    """Get current status for a site."""
    return _site_statuses.get(url)


def get_all_statuses() -> Dict[str, SiteStatus]:
    """Get all site statuses."""
    return _site_statuses.copy()


# ============================================
# HEALTH CHECKS
# ============================================

async def check_site(url: str) -> SiteStatus:
    """
    Check if a site is up and responding.

    Args:
        url: URL to check

    Returns:
        SiteStatus with results
    """
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    # Get or create status
    status = _site_statuses.get(url, SiteStatus(url=url, is_up=False))
    status.last_check = now

    try:
        start_time = datetime.now()

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT_SECONDS),
                allow_redirects=True
            ) as response:
                end_time = datetime.now()
                response_time = int((end_time - start_time).total_seconds() * 1000)

                status.status_code = response.status
                status.response_time_ms = response_time
                status.error_message = None

                if response.status == 200:
                    status.is_up = True
                    status.consecutive_failures = 0
                elif response.status < 500:
                    status.is_up = True
                    status.consecutive_failures = 0
                else:
                    status.is_up = False
                    status.consecutive_failures += 1
                    status.error_message = f"HTTP {response.status}"

    except asyncio.TimeoutError:
        status.is_up = False
        status.consecutive_failures += 1
        status.error_message = "Timeout"
        status.status_code = None
        status.response_time_ms = None

    except aiohttp.ClientError as e:
        status.is_up = False
        status.consecutive_failures += 1
        status.error_message = str(e)[:100]
        status.status_code = None
        status.response_time_ms = None

    except Exception as e:
        status.is_up = False
        status.consecutive_failures += 1
        status.error_message = str(e)[:100]
        status.status_code = None
        status.response_time_ms = None

    _site_statuses[url] = status
    return status


async def check_all_sites() -> List[SiteStatus]:
    """
    Check all deployable project sites.

    Returns:
        List of SiteStatus results
    """
    results = []

    for project in get_vercel_projects():
        if project.url:
            status = await check_site(project.url)
            results.append(status)
            # Small delay between checks
            await asyncio.sleep(1)

    return results


# ============================================
# ALERTING
# ============================================

def should_alert(status: SiteStatus) -> bool:
    """
    Determine if we should send an alert for this status.
    """
    # Must be down
    if status.is_up:
        return False

    # Need at least 2 consecutive failures
    if status.consecutive_failures < 2:
        return False

    # Check cooldown
    if status.last_alert:
        tz = pytz.timezone(TIMEZONE)
        now = datetime.now(tz)
        cooldown = timedelta(minutes=ALERT_COOLDOWN_MINUTES)
        if now - status.last_alert < cooldown:
            return False

    return True


def format_alert(status: SiteStatus, project_name: str = None) -> str:
    """Format an alert message."""
    name = project_name or status.url

    if status.error_message:
        return f"⚠️ **{name}** is DOWN\nError: {status.error_message}\nURL: {status.url}"
    else:
        return f"⚠️ **{name}** is DOWN\nStatus: {status.status_code}\nURL: {status.url}"


def format_recovery(status: SiteStatus, project_name: str = None) -> str:
    """Format a recovery message."""
    name = project_name or status.url
    rt = f" ({status.response_time_ms}ms)" if status.response_time_ms else ""
    return f"✅ **{name}** is back UP{rt}"


def format_slow_warning(status: SiteStatus, project_name: str = None) -> str:
    """Format a slow response warning."""
    name = project_name or status.url
    return f"🐢 **{name}** is slow ({status.response_time_ms}ms)"


# ============================================
# MONITORING LOOP
# ============================================

async def run_monitoring_check(send_callback: Optional[Callable] = None) -> List[str]:
    """
    Run a full monitoring check and generate alerts.

    Args:
        send_callback: Async function to send alerts

    Returns:
        List of alert messages generated
    """
    alerts = []
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    logger.info("Running site monitoring check")

    for project in get_vercel_projects():
        if not project.url:
            continue

        # Check the site
        old_status = _site_statuses.get(project.url)
        was_down = old_status and not old_status.is_up

        status = await check_site(project.url)

        # Check for state transitions and issues
        if should_alert(status):
            alert_msg = format_alert(status, project.name)
            alerts.append(alert_msg)
            status.last_alert = now
            _site_statuses[project.url] = status

            if send_callback:
                await send_callback(alert_msg)

            logger.warning(f"Site down alert: {project.name}")

        elif status.is_up and was_down:
            # Recovery
            recovery_msg = format_recovery(status, project.name)
            alerts.append(recovery_msg)

            if send_callback:
                await send_callback(recovery_msg)

            logger.info(f"Site recovered: {project.name}")

        elif status.is_up and status.response_time_ms and status.response_time_ms > SLOW_THRESHOLD_MS:
            # Slow response (don't alert every time, just log)
            logger.warning(f"Slow response from {project.name}: {status.response_time_ms}ms")

        # Small delay between checks
        await asyncio.sleep(1)

    return alerts


async def start_monitoring_loop(send_callback: Optional[Callable] = None):
    """
    Start the monitoring loop.

    Args:
        send_callback: Async function to send alerts
    """
    logger.info(f"Starting monitoring loop (every {CHECK_INTERVAL_MINUTES} minutes)")

    while True:
        try:
            await run_monitoring_check(send_callback)
        except Exception as e:
            logger.error(f"Monitoring check error: {e}")

        await asyncio.sleep(CHECK_INTERVAL_MINUTES * 60)


# ============================================
# STATUS REPORT
# ============================================

def generate_status_report() -> str:
    """Generate a status report for all monitored sites."""
    if not _site_statuses:
        return "No sites monitored yet"

    lines = ["**Site Status Report**\n"]

    for url, status in _site_statuses.items():
        # Find project name
        project_name = url
        for p in PROJECTS.values():
            if p.url == url:
                project_name = p.name
                break

        if status.is_up:
            emoji = "🟢"
            rt = f" ({status.response_time_ms}ms)" if status.response_time_ms else ""
            lines.append(f"{emoji} **{project_name}**{rt}")
        else:
            emoji = "🔴"
            error = f" - {status.error_message}" if status.error_message else ""
            lines.append(f"{emoji} **{project_name}**{error}")

    return "\n".join(lines)


async def quick_check(url: str) -> str:
    """
    Quick check a single URL and return status string.
    """
    status = await check_site(url)

    if status.is_up:
        rt = f" in {status.response_time_ms}ms" if status.response_time_ms else ""
        return f"✅ Site is UP{rt}"
    else:
        error = f": {status.error_message}" if status.error_message else ""
        return f"❌ Site is DOWN{error}"
