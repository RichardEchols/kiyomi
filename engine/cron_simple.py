"""
Kiyomi v5.0 — Simple Cron Runner
Reads ~/.kiyomi/cron.json and fires messages via CLI at scheduled times.
"""
import json
import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path

from engine.config import CONFIG_DIR, WORKSPACE, load_config
from engine.cli_adapter import get_adapter, sync_identity_file, get_env

logger = logging.getLogger("kiyomi.cron")
CRON_FILE = CONFIG_DIR / "cron.json"


def load_crons() -> list[dict]:
    """Load cron jobs from cron.json."""
    if CRON_FILE.exists():
        try:
            with open(CRON_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return []


def save_crons(crons: list[dict]):
    """Save cron jobs."""
    with open(CRON_FILE, "w") as f:
        json.dump(crons, f, indent=2)


def should_run(cron: dict, now: datetime) -> bool:
    """Check if a cron job should run at this time.

    Simple format: {"hour": 9, "minute": 0, "days": ["mon","tue","wed","thu","fri"]}
    """
    day_name = now.strftime("%a").lower()[:3]
    days = cron.get("days", ["mon", "tue", "wed", "thu", "fri", "sat", "sun"])
    if day_name not in days:
        return False
    return now.hour == cron.get("hour", 9) and now.minute == cron.get("minute", 0)


def run_cron(cron: dict):
    """Execute a cron job by sending its prompt to the CLI."""
    config = load_config()
    cli_name = config.get("cli", "")
    if not cli_name:
        return

    adapter = get_adapter(cli_name)
    sync_identity_file(cli_name, WORKSPACE)

    prompt = cron.get("prompt", "")
    if not prompt:
        return

    try:
        cmd = adapter.build_command(message=prompt)
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=120, cwd=str(WORKSPACE), env=get_env(),
        )
        text, _ = adapter.parse_response(result.stdout, result.stderr, result.returncode)
        logger.info(f"Cron '{cron.get('name', '?')}' ran: {text[:100]}")
        return text
    except Exception as e:
        logger.error(f"Cron error: {e}")
        return None


def tick():
    """Check and run any due cron jobs. Call this once per minute."""
    now = datetime.now()
    for cron in load_crons():
        if should_run(cron, now):
            run_cron(cron)
