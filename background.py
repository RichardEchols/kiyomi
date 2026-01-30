"""
Kiyomi Background - Supervisor + heartbeat, reminders, morning brief, monitoring loops.
"""
import asyncio
import json
import logging
import re
import aiohttp
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Coroutine, Any, Dict, List, Optional

import pytz

from config import (
    TIMEZONE, BASE_DIR, WORKSPACE_DIR, MEMORY_DIR,
    HEARTBEAT_INTERVAL_MINUTES, HEARTBEAT_FILE,
    MORNING_BRIEF_HOUR, MORNING_BRIEF_MINUTE,
    QUIET_HOURS_START, QUIET_HOURS_END,
    BOT_EMOJI,
)

logger = logging.getLogger(__name__)

# Import nightly config with fallback
try:
    from config import NIGHTLY_WORK_HOUR, NIGHTLY_WORK_MINUTE
except ImportError:
    NIGHTLY_WORK_HOUR = 1
    NIGHTLY_WORK_MINUTE = 0


# ══════════════════════════════════════════════════════════════
# SUPERVISOR (copied verbatim from supervisor.py)
# ══════════════════════════════════════════════════════════════

class SupervisedTask:
    """A background task with auto-restart on crash."""

    def __init__(
        self,
        name: str,
        coro_factory: Callable[..., Coroutine[Any, Any, None]],
        args: tuple = (),
        max_restarts: int = 50,
        base_delay: float = 5.0,
        max_delay: float = 300.0,
    ):
        self.name = name
        self._coro_factory = coro_factory
        self._args = args
        self._max_restarts = max_restarts
        self._base_delay = base_delay
        self._max_delay = max_delay

        self._task: Optional[asyncio.Task] = None
        self._restarts = 0
        self._running = False
        self._started_at: Optional[datetime] = None
        self._last_crash: Optional[datetime] = None
        self._last_error: str = ""

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._supervise())
        logger.info(f"[supervisor] Started: {self.name}")

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info(f"[supervisor] Stopped: {self.name}")

    async def _supervise(self) -> None:
        delay = self._base_delay
        while self._running and self._restarts < self._max_restarts:
            self._started_at = datetime.now()
            try:
                await self._coro_factory(*self._args)
                logger.info(f"[supervisor] {self.name} completed normally")
                break
            except asyncio.CancelledError:
                logger.info(f"[supervisor] {self.name} cancelled")
                break
            except Exception as e:
                self._restarts += 1
                self._last_crash = datetime.now()
                self._last_error = str(e)[:200]
                logger.error(
                    f"[supervisor] {self.name} crashed "
                    f"(restart {self._restarts}/{self._max_restarts}): {e}"
                )
                if not self._running:
                    break
                logger.info(f"[supervisor] Restarting {self.name} in {delay:.0f}s...")
                await asyncio.sleep(delay)
                delay = min(delay * 2, self._max_delay)
                if self._started_at and (datetime.now() - self._started_at).total_seconds() > 300:
                    delay = self._base_delay

        if self._restarts >= self._max_restarts:
            logger.critical(
                f"[supervisor] {self.name} exceeded max restarts ({self._max_restarts}). Giving up."
            )

    @property
    def status(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "running": self._running and self._task and not self._task.done(),
            "restarts": self._restarts,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "last_crash": self._last_crash.isoformat() if self._last_crash else None,
            "last_error": self._last_error,
        }


class Supervisor:
    def __init__(self):
        self._tasks: Dict[str, SupervisedTask] = {}

    def add(self, name: str, coro_factory, args: tuple = (), **kwargs):
        self._tasks[name] = SupervisedTask(name, coro_factory, args, **kwargs)

    async def start_all(self):
        for task in self._tasks.values():
            await task.start()
        logger.info(f"[supervisor] All {len(self._tasks)} tasks started")

    async def stop_all(self):
        logger.info(f"[supervisor] Stopping all {len(self._tasks)} tasks...")
        await asyncio.gather(*(t.stop() for t in self._tasks.values()), return_exceptions=True)
        logger.info("[supervisor] All tasks stopped")

    def status(self) -> List[Dict[str, Any]]:
        return [t.status for t in self._tasks.values()]


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════

_last_message_time: Optional[datetime] = None


def update_last_message_time():
    global _last_message_time
    _last_message_time = datetime.now(pytz.timezone(TIMEZONE))


def _is_active(minutes: int = 5) -> bool:
    if _last_message_time is None:
        return False
    tz = pytz.timezone(TIMEZONE)
    return _last_message_time > datetime.now(tz) - timedelta(minutes=minutes)


def _is_quiet() -> bool:
    hour = datetime.now(pytz.timezone(TIMEZONE)).hour
    if QUIET_HOURS_START > QUIET_HOURS_END:
        return hour >= QUIET_HOURS_START or hour < QUIET_HOURS_END
    return QUIET_HOURS_START <= hour < QUIET_HOURS_END


# Persist morning brief date to survive restarts
_BRIEF_STATE = WORKSPACE_DIR / ".morning_brief_date"


def _brief_sent_today() -> bool:
    try:
        if _BRIEF_STATE.exists():
            tz = pytz.timezone(TIMEZONE)
            return _BRIEF_STATE.read_text().strip() == datetime.now(tz).strftime("%Y-%m-%d")
    except Exception:
        pass
    return False


def _mark_brief_sent():
    try:
        tz = pytz.timezone(TIMEZONE)
        tmp = _BRIEF_STATE.with_suffix(".tmp")
        tmp.write_text(datetime.now(tz).strftime("%Y-%m-%d"))
        tmp.rename(_BRIEF_STATE)
    except Exception as e:
        logger.error(f"Failed to save brief state: {e}")


# Persist nightly work date to survive restarts
_NIGHTLY_STATE = WORKSPACE_DIR / ".nightly_work_date"


def _nightly_done_today() -> bool:
    try:
        if _NIGHTLY_STATE.exists():
            tz = pytz.timezone(TIMEZONE)
            return _NIGHTLY_STATE.read_text().strip() == datetime.now(tz).strftime("%Y-%m-%d")
    except Exception:
        pass
    return False


def _mark_nightly_done():
    try:
        tz = pytz.timezone(TIMEZONE)
        tmp = _NIGHTLY_STATE.with_suffix(".tmp")
        tmp.write_text(datetime.now(tz).strftime("%Y-%m-%d"))
        tmp.rename(_NIGHTLY_STATE)
    except Exception as e:
        logger.error(f"Failed to save nightly state: {e}")


# ══════════════════════════════════════════════════════════════
# HEARTBEAT LOOP
# ══════════════════════════════════════════════════════════════

def _parse_heartbeat_tasks(content: str) -> List[Dict]:
    """Extract uncompleted tasks from HEARTBEAT.md."""
    tasks = []
    if not content:
        return tasks
    section = re.search(r'##\s*Pending\s*Tasks\s*\n(.*?)(?=\n##|$)', content, re.DOTALL | re.IGNORECASE)
    if not section:
        return tasks
    for m in re.finditer(r'-\s*\[\s*\]\s*(.+)', section.group(1)):
        tasks.append({"description": m.group(1).strip()})
    return tasks


async def _heartbeat_loop(send_cb):
    """Every 30 min: read HEARTBEAT.md, execute up to 2 pending tasks via Claude."""
    from router import route_to_claude

    while True:
        try:
            if _is_active(5) or _is_quiet():
                logger.info("Heartbeat: skipping (active chat or quiet hours)")
            else:
                content = HEARTBEAT_FILE.read_text() if HEARTBEAT_FILE.exists() else ""
                tasks = _parse_heartbeat_tasks(content)
                executed = 0
                for task in tasks[:2]:
                    logger.info(f"Heartbeat task: {task['description'][:50]}")
                    result, ok = await route_to_claude(task["description"])
                    if ok:
                        # Mark complete in file (atomic write)
                        old = f"- [ ] {task['description']}"
                        new = f"- [x] {task['description']}"
                        content = content.replace(old, new)
                        try:
                            tmp = HEARTBEAT_FILE.with_suffix(".tmp")
                            tmp.write_text(content)
                            tmp.replace(HEARTBEAT_FILE)
                        except Exception:
                            HEARTBEAT_FILE.write_text(content)
                        executed += 1
                if executed:
                    logger.info(f"Completed {executed} background task(s) silently")
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")

        await asyncio.sleep(HEARTBEAT_INTERVAL_MINUTES * 60)


# ══════════════════════════════════════════════════════════════
# REMINDER LOOP
# ══════════════════════════════════════════════════════════════

REMINDERS_FILE = BASE_DIR / "reminders.json"


def _load_reminders() -> List[Dict]:
    try:
        if REMINDERS_FILE.exists():
            with open(REMINDERS_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return []


def _save_reminders(reminders: List[Dict]):
    try:
        tmp = REMINDERS_FILE.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(reminders, f, indent=2)
        tmp.replace(REMINDERS_FILE)
    except Exception as e:
        logger.error(f"Error saving reminders: {e}")
        # Fallback: try direct write
        try:
            with open(REMINDERS_FILE, "w") as f:
                json.dump(reminders, f, indent=2)
        except Exception:
            pass


def add_reminder(message: str, remind_at: datetime, repeat: Optional[str] = None) -> str:
    reminders = _load_reminders()
    rid = f"rem_{int(datetime.now().timestamp())}"
    reminders.append({
        "id": rid,
        "message": message,
        "remind_at": remind_at.isoformat(),
        "repeat": repeat,
        "created": datetime.now().isoformat(),
        "sent": False,
    })
    _save_reminders(reminders)
    return rid


def remove_reminder(rid: str) -> bool:
    reminders = _load_reminders()
    before = len(reminders)
    reminders = [r for r in reminders if r["id"] != rid]
    if len(reminders) < before:
        _save_reminders(reminders)
        return True
    return False


def list_reminders() -> List[Dict]:
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    out = []
    for r in _load_reminders():
        rat = datetime.fromisoformat(r["remind_at"])
        if rat.tzinfo is None:
            rat = tz.localize(rat)
        if not r.get("sent") or r.get("repeat"):
            out.append({
                **r,
                "remind_at_formatted": rat.strftime("%Y-%m-%d %H:%M"),
                "is_due": rat <= now,
            })
    return sorted(out, key=lambda x: x["remind_at"])


def parse_reminder_time(time_str: str) -> Optional[datetime]:
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    s = time_str.lower().strip()

    if "in " in s and "minute" in s:
        try:
            return now + timedelta(minutes=int(s.split("in ")[1].split()[0]))
        except Exception:
            pass
    if "in " in s and "hour" in s:
        try:
            return now + timedelta(hours=int(s.split("in ")[1].split()[0]))
        except Exception:
            pass
    if "tomorrow" in s:
        tomorrow = now + timedelta(days=1)
        if "at " in s:
            try:
                tp = s.split("at ")[1].strip()
                h = int(tp.replace("am", "").replace("pm", "").replace(":", "").strip()[:2])
                if "pm" in tp and h != 12:
                    h += 12
                if "am" in tp and h == 12:
                    h = 0
                return tomorrow.replace(hour=h, minute=0, second=0, microsecond=0)
            except Exception:
                pass
        return tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
    if s.startswith("at "):
        try:
            tp = s[3:].strip()
            h = int(tp.replace("am", "").replace("pm", "").replace(":", "").strip()[:2])
            if "pm" in tp and h != 12:
                h += 12
            if "am" in tp and h == 12:
                h = 0
            result = now.replace(hour=h, minute=0, second=0, microsecond=0)
            if result <= now:
                result += timedelta(days=1)
            return result
        except Exception:
            pass
    return None


async def _reminder_loop(send_cb):
    """Every 60 sec: check reminders.json, send due ones, handle repeats.
    Defers delivery by up to 60s if Richard is actively chatting."""
    while True:
        try:
            # If Richard is mid-chat, wait for a pause before firing reminders
            if _is_active(1):
                await asyncio.sleep(60)
                continue

            tz = pytz.timezone(TIMEZONE)
            now = datetime.now(tz)
            reminders = _load_reminders()
            updated = []
            for r in reminders:
                rat = datetime.fromisoformat(r["remind_at"])
                if rat.tzinfo is None:
                    rat = tz.localize(rat)
                if rat <= now and not r.get("sent"):
                    try:
                        await send_cb(f"⏰ **Reminder:** {r['message']}")
                    except Exception as e:
                        logger.error(f"Error sending reminder: {e}")
                    if r.get("repeat") == "daily":
                        r["remind_at"] = (rat + timedelta(days=1)).isoformat()
                        r["sent"] = False
                    elif r.get("repeat") == "weekly":
                        r["remind_at"] = (rat + timedelta(weeks=1)).isoformat()
                        r["sent"] = False
                    else:
                        r["sent"] = True
                updated.append(r)
            _save_reminders(updated)
        except Exception as e:
            logger.error(f"Reminder loop error: {e}")

        await asyncio.sleep(60)


# ══════════════════════════════════════════════════════════════
# MORNING BRIEF
# ══════════════════════════════════════════════════════════════

async def _morning_brief_loop(send_cb):
    """At 8:30 AM, call Claude to generate morning brief. Pauses if Richard is chatting."""
    from router import route_to_claude

    while True:
        try:
            tz = pytz.timezone(TIMEZONE)
            now = datetime.now(tz)

            if not _brief_sent_today():
                in_window = (
                    (now.hour == MORNING_BRIEF_HOUR and now.minute >= MORNING_BRIEF_MINUTE)
                    or (now.hour == MORNING_BRIEF_HOUR + 1 and now.minute < 30)
                )
                if in_window and _is_active(2):
                    logger.info("Morning brief deferred — Richard is chatting")
                    await asyncio.sleep(120)
                    continue
                if in_window:
                    logger.info("Generating morning brief...")
                    brief_prompt = (
                        "Generate Richard's morning brief. Include:\n"
                        "1. Daily Text from wol.jw.org (FULL TEXT)\n"
                        "2. Weather for Atlanta\n"
                        "3. Any overnight work summary\n"
                        "4. ScribbleStokes video idea\n"
                        "5. @RichardBEchols vibe coding video idea\n"
                        "6. App idea of the day\n"
                        "7. US Politics (3 brief stories)\n"
                        "8. World News (3 brief stories)\n"
                        "9. AI & Tech news\n"
                        "10. Tasks and priorities from COMMITMENTS.md\n\n"
                        "Format nicely for Telegram. Keep each section concise."
                    )
                    result, ok = await route_to_claude(brief_prompt)
                    if ok:
                        await send_cb(f"{BOT_EMOJI} Good morning, Richard!\n\n{result}")
                    else:
                        await send_cb(f"{BOT_EMOJI} Morning brief had trouble: {result[:200]}")
                    _mark_brief_sent()
        except Exception as e:
            logger.error(f"Morning brief error: {e}")

        await asyncio.sleep(300)  # check every 5 min


# ══════════════════════════════════════════════════════════════
# MONITORING LOOP
# ══════════════════════════════════════════════════════════════

_site_failures: Dict[str, int] = {}  # url -> consecutive failures


async def _monitoring_loop(send_cb):
    """Every 30 min: HTTP-check project URLs from projects.json. Alert after 2 failures.
    Pauses if Richard is actively chatting."""
    projects_file = BASE_DIR / "projects.json"

    while True:
        try:
            if _is_active(2):
                logger.info("Monitoring deferred — Richard is chatting")
                await asyncio.sleep(120)
                continue

            if not projects_file.exists():
                await asyncio.sleep(1800)
                continue

            with open(projects_file) as f:
                projects = json.load(f)

            for pid, proj in projects.items():
                url = proj.get("url")
                if not url:
                    continue
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            url,
                            timeout=aiohttp.ClientTimeout(total=10),
                            allow_redirects=True,
                        ) as resp:
                            if resp.status < 500:
                                if _site_failures.get(url, 0) >= 2:
                                    await send_cb(f"✅ **{proj['name']}** is back up")
                                _site_failures[url] = 0
                            else:
                                _site_failures[url] = _site_failures.get(url, 0) + 1
                except Exception:
                    _site_failures[url] = _site_failures.get(url, 0) + 1

                failures = _site_failures.get(url, 0)
                if failures == 2:
                    await send_cb(f"⚠️ **{proj['name']}** is DOWN ({url})")

                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Monitoring error: {e}")

        await asyncio.sleep(1800)  # 30 min


# ══════════════════════════════════════════════════════════════
# NIGHTLY AUTONOMOUS WORK
# ══════════════════════════════════════════════════════════════

async def _nightly_work_loop(send_cb):
    """At 2:30 AM EST, kick off autonomous nightly work session via Claude CLI.

    Reads COMMITMENTS.md for priorities, picks work to do, creates PRs.
    Writes results to memory/YYYY-MM-DD-overnight.md.
    """
    from router import route_to_claude

    while True:
        try:
            tz = pytz.timezone(TIMEZONE)
            now = datetime.now(tz)

            if not _nightly_done_today():
                in_window = (
                    (now.hour == NIGHTLY_WORK_HOUR and now.minute >= NIGHTLY_WORK_MINUTE)
                    or (now.hour == NIGHTLY_WORK_HOUR + 1 and now.minute < 30)
                )
                if in_window and _is_active(10):
                    logger.info("Nightly work deferred — Richard is still active")
                    await asyncio.sleep(300)
                    continue
                if in_window:
                    logger.info("Starting nightly autonomous work session...")
                    await send_cb(f"{BOT_EMOJI} Starting nightly work session (2:30 AM). I'll report back in the morning.")

                    # Read commitments for priorities
                    commitments_file = WORKSPACE_DIR / "COMMITMENTS.md"
                    commitments = ""
                    if commitments_file.exists():
                        commitments = commitments_file.read_text()

                    # Read today's memory for context
                    today_str = now.strftime("%Y-%m-%d")
                    today_memory = MEMORY_DIR / f"{today_str}.md"
                    recent_context = ""
                    if today_memory.exists():
                        recent_context = today_memory.read_text()[-2000:]

                    nightly_prompt = (
                        "You are Kiyomi running your NIGHTLY AUTONOMOUS WORK session.\n"
                        "It is 2:30 AM EST. Richard is asleep. Work autonomously.\n\n"
                        "RULES:\n"
                        "- Create branches and PRs ONLY. Never push to main/prod.\n"
                        "- Write your overnight report to memory/ when done.\n"
                        "- Follow the priority order from COMMITMENTS.md.\n"
                        "- Be productive — Richard wants to wake up to meaningful progress.\n\n"
                        f"COMMITMENTS:\n{commitments}\n\n"
                        f"TODAY'S CONTEXT (last 2000 chars):\n{recent_context}\n\n"
                        "INSTRUCTIONS:\n"
                        "1. Check all projects for known issues or improvements.\n"
                        "2. Pick the highest-priority work you can do.\n"
                        "3. Do the work. Create PRs on feature branches.\n"
                        "4. Write a summary to the overnight memory file.\n"
                        "5. Report what you accomplished.\n"
                    )

                    result, ok = await route_to_claude(nightly_prompt)

                    # Write overnight report
                    overnight_file = MEMORY_DIR / f"{today_str}-overnight.md"
                    try:
                        report = f"# Overnight Work Report - {today_str}\n\n"
                        report += f"**Started:** {now.strftime('%H:%M %Z')}\n"
                        report += f"**Status:** {'Success' if ok else 'Partial/Error'}\n\n"
                        report += "## Results\n\n"
                        report += result[:5000] if result else "No output captured."
                        overnight_file.write_text(report)
                    except Exception as e:
                        logger.error(f"Failed to write overnight report: {e}")

                    _mark_nightly_done()
                    logger.info("Nightly work session complete")

                    if ok:
                        # Truncate for Telegram (4096 char limit)
                        summary = result[:3000] if result else "Work completed, no details captured."
                        await send_cb(f"{BOT_EMOJI} Nightly work done. Full report saved to memory.\n\n{summary}")
                    else:
                        await send_cb(f"{BOT_EMOJI} Nightly work finished with issues: {result[:500]}")

        except Exception as e:
            logger.error(f"Nightly work error: {e}")

        await asyncio.sleep(300)  # check every 5 min


# ══════════════════════════════════════════════════════════════
# REGISTRATION
# ══════════════════════════════════════════════════════════════

def register_all(supervisor: Supervisor, send_cb):
    """Wire all background loops into the supervisor."""
    supervisor.add("heartbeat", _heartbeat_loop, args=(send_cb,))
    supervisor.add("reminders", _reminder_loop, args=(send_cb,))
    # Morning brief discontinued — Brock handles this now (2026-01-30)
    # supervisor.add("morning_brief", _morning_brief_loop, args=(send_cb,))
    supervisor.add("monitoring", _monitoring_loop, args=(send_cb,))
    supervisor.add("nightly_work", _nightly_work_loop, args=(send_cb,))
