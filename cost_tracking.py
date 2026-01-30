"""
Kiyomi Cost Tracking - Monitor API usage and spending

Features:
- Track API calls and estimated costs
- Set spending alerts
- Daily/weekly cost reports
- Cost per project tracking
"""
import asyncio
import logging
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Callable

import pytz
from config import BASE_DIR, TIMEZONE

logger = logging.getLogger(__name__)

# Cost tracking configuration
COST_LOG_FILE = BASE_DIR / "cost_log.json"
COST_ALERTS_FILE = BASE_DIR / "cost_alerts.json"

# Estimated costs per 1M tokens (as of 2024)
# These are rough estimates and should be updated periodically
API_COSTS = {
    "claude-opus-4-5": {"input": 15.00, "output": 75.00},     # per 1M tokens
    "claude-sonnet-4": {"input": 3.00, "output": 15.00},
    "claude-haiku-3.5": {"input": 0.25, "output": 1.25},
    "claude-3-opus": {"input": 15.00, "output": 75.00},
    "claude-3-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-4o": {"input": 5.00, "output": 15.00},
    "elevenlabs-tts": {"per_char": 0.00003},  # Rough estimate
}

# Default daily budget alert
DEFAULT_DAILY_BUDGET = 10.00  # $10/day


@dataclass
class APICall:
    """Represents a single API call."""
    timestamp: datetime
    model: str
    input_tokens: int
    output_tokens: int
    cost: float
    project: Optional[str] = None
    task_type: Optional[str] = None  # e.g., "chat", "deploy", "swarm"


@dataclass
class CostAlert:
    """Represents a cost alert configuration."""
    alert_type: str  # "daily", "weekly", "monthly", "per_task"
    threshold: float
    enabled: bool = True
    last_triggered: Optional[datetime] = None


# Global state
_cost_log: List[Dict] = []
_alerts: Dict[str, CostAlert] = {}
_daily_totals: Dict[str, float] = {}  # date -> total


def _load_cost_log() -> None:
    """Load cost log from file."""
    global _cost_log, _daily_totals
    try:
        if COST_LOG_FILE.exists():
            with open(COST_LOG_FILE) as f:
                _cost_log = json.load(f)

            # Rebuild daily totals
            _daily_totals = {}
            for entry in _cost_log:
                date = entry.get("timestamp", "")[:10]
                _daily_totals[date] = _daily_totals.get(date, 0) + entry.get("cost", 0)
    except Exception as e:
        logger.error(f"Error loading cost log: {e}")
        _cost_log = []


def _save_cost_log() -> None:
    """Save cost log to file."""
    try:
        # Keep only last 1000 entries
        recent = _cost_log[-1000:]
        with open(COST_LOG_FILE, "w") as f:
            json.dump(recent, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving cost log: {e}")


def _load_alerts() -> None:
    """Load alert configurations."""
    global _alerts
    try:
        if COST_ALERTS_FILE.exists():
            with open(COST_ALERTS_FILE) as f:
                data = json.load(f)
                _alerts = {
                    k: CostAlert(
                        alert_type=v["alert_type"],
                        threshold=v["threshold"],
                        enabled=v.get("enabled", True),
                        last_triggered=datetime.fromisoformat(v["last_triggered"]) if v.get("last_triggered") else None
                    )
                    for k, v in data.items()
                }
        else:
            # Set default alerts
            _alerts = {
                "daily": CostAlert(alert_type="daily", threshold=DEFAULT_DAILY_BUDGET),
                "per_task": CostAlert(alert_type="per_task", threshold=1.00)
            }
            _save_alerts()
    except Exception as e:
        logger.error(f"Error loading alerts: {e}")
        _alerts = {}


def _save_alerts() -> None:
    """Save alert configurations."""
    try:
        data = {
            k: {
                "alert_type": v.alert_type,
                "threshold": v.threshold,
                "enabled": v.enabled,
                "last_triggered": v.last_triggered.isoformat() if v.last_triggered else None
            }
            for k, v in _alerts.items()
        }
        with open(COST_ALERTS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving alerts: {e}")


def estimate_tokens(text: str) -> int:
    """Estimate token count for text (rough approximation)."""
    # Rough estimate: 1 token ≈ 4 characters for English
    return len(text) // 4


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int
) -> float:
    """
    Estimate cost for an API call.
    Returns cost in USD.
    """
    # Find matching model
    model_lower = model.lower()
    costs = None

    for model_key, model_costs in API_COSTS.items():
        if model_key in model_lower:
            costs = model_costs
            break

    if not costs:
        # Default to Claude Opus pricing (conservative estimate)
        costs = API_COSTS["claude-opus-4-5"]

    # Calculate cost (costs are per 1M tokens)
    if "input" in costs and "output" in costs:
        input_cost = (input_tokens / 1_000_000) * costs["input"]
        output_cost = (output_tokens / 1_000_000) * costs["output"]
        return round(input_cost + output_cost, 6)

    return 0.0


def log_api_call(
    model: str,
    input_tokens: int,
    output_tokens: int,
    project: Optional[str] = None,
    task_type: Optional[str] = None
) -> float:
    """
    Log an API call and return estimated cost.
    """
    tz = pytz.timezone(TIMEZONE)
    timestamp = datetime.now(tz)

    cost = estimate_cost(model, input_tokens, output_tokens)

    entry = {
        "timestamp": timestamp.isoformat(),
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost": cost,
        "project": project,
        "task_type": task_type
    }

    _cost_log.append(entry)

    # Update daily total
    date = timestamp.strftime("%Y-%m-%d")
    _daily_totals[date] = _daily_totals.get(date, 0) + cost

    _save_cost_log()

    return cost


async def check_alerts(send_callback: Optional[Callable] = None) -> List[str]:
    """
    Check if any cost alerts should fire.
    Returns list of alert messages.
    """
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    today = now.strftime("%Y-%m-%d")

    triggered = []

    # Check daily alert
    if "daily" in _alerts and _alerts["daily"].enabled:
        daily_total = _daily_totals.get(today, 0)
        if daily_total >= _alerts["daily"].threshold:
            # Check if already triggered today
            if _alerts["daily"].last_triggered is None or \
               _alerts["daily"].last_triggered.strftime("%Y-%m-%d") != today:
                msg = f"💰 **Daily Cost Alert**\n\nToday's spending: ${daily_total:.2f}\nThreshold: ${_alerts['daily'].threshold:.2f}"
                triggered.append(msg)
                _alerts["daily"].last_triggered = now
                _save_alerts()

    if triggered and send_callback:
        for msg in triggered:
            await send_callback(msg)

    return triggered


def get_daily_cost(date: Optional[str] = None) -> float:
    """Get total cost for a day."""
    if date is None:
        tz = pytz.timezone(TIMEZONE)
        date = datetime.now(tz).strftime("%Y-%m-%d")
    return _daily_totals.get(date, 0)


def get_weekly_cost() -> float:
    """Get total cost for the current week."""
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    total = 0
    for i in range(7):
        date = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        total += _daily_totals.get(date, 0)

    return total


def get_monthly_cost() -> float:
    """Get total cost for the current month."""
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    month_prefix = now.strftime("%Y-%m")

    total = 0
    for date, cost in _daily_totals.items():
        if date.startswith(month_prefix):
            total += cost

    return total


def get_cost_by_project() -> Dict[str, float]:
    """Get costs grouped by project."""
    by_project = {}

    for entry in _cost_log:
        project = entry.get("project") or "unknown"
        by_project[project] = by_project.get(project, 0) + entry.get("cost", 0)

    return by_project


def get_cost_by_task_type() -> Dict[str, float]:
    """Get costs grouped by task type."""
    by_type = {}

    for entry in _cost_log:
        task_type = entry.get("task_type") or "general"
        by_type[task_type] = by_type.get(task_type, 0) + entry.get("cost", 0)

    return by_type


def generate_cost_report() -> str:
    """Generate a comprehensive cost report."""
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    today = now.strftime("%Y-%m-%d")

    daily = get_daily_cost()
    weekly = get_weekly_cost()
    monthly = get_monthly_cost()

    by_project = get_cost_by_project()
    by_type = get_cost_by_task_type()

    # Recent calls
    recent_calls = _cost_log[-10:]

    report = f"""💰 **Kiyomi Cost Report**
_{now.strftime("%Y-%m-%d %H:%M %Z")}_

**Spending Summary:**
• Today: ${daily:.2f}
• This Week: ${weekly:.2f}
• This Month: ${monthly:.2f}

**By Project:**
"""

    for project, cost in sorted(by_project.items(), key=lambda x: -x[1])[:5]:
        report += f"• {project}: ${cost:.2f}\n"

    report += "\n**By Task Type:**\n"
    for task_type, cost in sorted(by_type.items(), key=lambda x: -x[1])[:5]:
        report += f"• {task_type}: ${cost:.2f}\n"

    report += "\n**Recent Calls:**\n"
    for call in recent_calls[-5:]:
        time = call.get("timestamp", "")[-8:-3]  # HH:MM
        cost = call.get("cost", 0)
        model = call.get("model", "unknown")[:20]
        report += f"• {time} - ${cost:.4f} ({model})\n"

    # Alert status
    daily_alert = _alerts.get("daily")
    if daily_alert:
        percent = (daily / daily_alert.threshold) * 100 if daily_alert.threshold > 0 else 0
        report += f"\n**Daily Budget:** ${daily:.2f} / ${daily_alert.threshold:.2f} ({percent:.0f}%)"

    return report


def set_daily_budget(amount: float) -> bool:
    """Set the daily budget alert threshold."""
    try:
        if "daily" not in _alerts:
            _alerts["daily"] = CostAlert(alert_type="daily", threshold=amount)
        else:
            _alerts["daily"].threshold = amount
        _save_alerts()
        return True
    except Exception as e:
        logger.error(f"Error setting daily budget: {e}")
        return False


def get_alert_settings() -> Dict:
    """Get current alert settings."""
    return {
        k: {
            "type": v.alert_type,
            "threshold": v.threshold,
            "enabled": v.enabled
        }
        for k, v in _alerts.items()
    }


# Initialize on module load
_load_cost_log()
_load_alerts()
