"""
Kiyomi Smart Escalation - Intelligent error handling and escalation

Features:
- Try to fix issues automatically first
- Build rich context when escalating
- Smart filtering of what needs Richard's attention
- Track escalation history to avoid repeating
"""
import asyncio
import logging
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Callable, Tuple
from enum import Enum

import pytz
from config import BASE_DIR, TIMEZONE

logger = logging.getLogger(__name__)

# Escalation configuration
ESCALATION_LOG_FILE = BASE_DIR / "escalation_log.json"
MAX_AUTO_FIX_ATTEMPTS = 3
ESCALATION_COOLDOWN_MINUTES = 30  # Don't re-escalate same issue within this time


class EscalationType(Enum):
    DEPLOY_FAILURE = "deploy_failure"
    BUILD_ERROR = "build_error"
    SITE_DOWN = "site_down"
    API_ERROR = "api_error"
    TASK_FAILURE = "task_failure"
    SECURITY_ALERT = "security_alert"
    COST_ALERT = "cost_alert"
    UNKNOWN = "unknown"


class Severity(Enum):
    LOW = "low"           # Informational, don't bother Richard
    MEDIUM = "medium"     # Try to fix, escalate if can't
    HIGH = "high"         # Escalate with context
    CRITICAL = "critical" # Escalate immediately


@dataclass
class EscalationContext:
    """Rich context for an escalation."""
    escalation_type: EscalationType
    severity: Severity
    title: str
    description: str
    error_details: Optional[str] = None
    affected_project: Optional[str] = None
    affected_url: Optional[str] = None
    auto_fix_attempts: int = 0
    auto_fix_results: List[str] = field(default_factory=list)
    suggested_actions: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(pytz.timezone(TIMEZONE)))
    escalated: bool = False
    resolved: bool = False
    resolution: Optional[str] = None


# Track recent escalations to avoid spam
_recent_escalations: Dict[str, datetime] = {}
_escalation_history: List[EscalationContext] = []


def classify_error(error_text: str, context: Optional[str] = None) -> Tuple[EscalationType, Severity]:
    """
    Classify an error into type and severity.
    """
    error_lower = error_text.lower()

    # Deployment failures
    if any(p in error_lower for p in ["vercel", "deploy", "deployment failed"]):
        return EscalationType.DEPLOY_FAILURE, Severity.HIGH

    # Build errors
    if any(p in error_lower for p in ["build failed", "npm run build", "compilation error", "syntax error"]):
        return EscalationType.BUILD_ERROR, Severity.MEDIUM

    # Site down
    if any(p in error_lower for p in ["site down", "503", "502", "500 error", "connection refused", "timeout"]):
        return EscalationType.SITE_DOWN, Severity.HIGH

    # API errors
    if any(p in error_lower for p in ["api error", "rate limit", "quota exceeded", "unauthorized", "401", "403"]):
        if "rate limit" in error_lower or "quota" in error_lower:
            return EscalationType.API_ERROR, Severity.MEDIUM
        return EscalationType.API_ERROR, Severity.HIGH

    # Security alerts
    if any(p in error_lower for p in ["security", "unauthorized access", "suspicious", "breach"]):
        return EscalationType.SECURITY_ALERT, Severity.CRITICAL

    # Cost alerts
    if any(p in error_lower for p in ["cost", "billing", "usage limit", "spending"]):
        return EscalationType.COST_ALERT, Severity.MEDIUM

    # Default
    return EscalationType.UNKNOWN, Severity.LOW


def _get_escalation_key(escalation: EscalationContext) -> str:
    """Generate a unique key for an escalation to prevent duplicates."""
    return f"{escalation.escalation_type.value}:{escalation.affected_project or 'none'}:{escalation.title[:50]}"


def _should_escalate(escalation: EscalationContext) -> bool:
    """Determine if we should escalate (check cooldown)."""
    key = _get_escalation_key(escalation)

    if key in _recent_escalations:
        last_time = _recent_escalations[key]
        if datetime.now(pytz.timezone(TIMEZONE)) - last_time < timedelta(minutes=ESCALATION_COOLDOWN_MINUTES):
            logger.info(f"Escalation {key} in cooldown, skipping")
            return False

    return True


async def try_auto_fix(escalation: EscalationContext) -> Tuple[bool, str]:
    """
    Try to automatically fix an issue.
    Returns (fixed, result_message).
    """
    if escalation.auto_fix_attempts >= MAX_AUTO_FIX_ATTEMPTS:
        return False, "Max auto-fix attempts reached"

    escalation.auto_fix_attempts += 1

    # Build auto-fix prompt based on error type
    fix_prompts = {
        EscalationType.DEPLOY_FAILURE: """
Try to fix this deployment failure:
1. Check build logs for errors
2. Fix any syntax or import errors
3. Redeploy with --force flag
4. Verify deployment succeeded
""",
        EscalationType.BUILD_ERROR: """
Try to fix this build error:
1. Read the error message carefully
2. Find the file with the error
3. Fix the syntax/import/type error
4. Run build again to verify
""",
        EscalationType.SITE_DOWN: """
Try to fix this site being down:
1. Check Vercel dashboard for issues
2. Check recent deployments
3. If recent deploy broke it, rollback
4. Verify site is back up
""",
        EscalationType.API_ERROR: """
Try to fix this API error:
1. Check if it's a rate limit (wait)
2. Check API keys in .env.local
3. Check if service is down
4. Report status
""",
    }

    fix_prompt = fix_prompts.get(escalation.escalation_type, "")
    if not fix_prompt:
        return False, "No auto-fix strategy for this error type"

    full_prompt = f"""ISSUE: {escalation.title}
DETAILS: {escalation.error_details or escalation.description}
PROJECT: {escalation.affected_project or 'Unknown'}

{fix_prompt}

Try to fix this issue. Be autonomous - make decisions and take action.
After attempting the fix, report what you did and whether it worked."""

    try:
        # Determine working directory
        working_dir = "/Users/richardecholsai2/Apps"
        if escalation.affected_project:
            from projects import get_project_by_name
            project = get_project_by_name(escalation.affected_project)
            if project:
                working_dir = project.path

        process = await asyncio.create_subprocess_exec(
            "/Users/richardecholsai2/.local/bin/claude",
            "-p", full_prompt,
            "--dangerously-skip-permissions",
            cwd=working_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=300)  # 5 min timeout
        result = stdout.decode("utf-8", errors="replace").strip()

        escalation.auto_fix_results.append(result[:500])

        # Check if fix was successful
        success_indicators = ["fixed", "resolved", "working", "deployed successfully", "site is up"]
        if any(ind in result.lower() for ind in success_indicators):
            escalation.resolved = True
            escalation.resolution = result[:200]
            return True, result

        return False, result

    except asyncio.TimeoutError:
        return False, "Auto-fix attempt timed out"
    except Exception as e:
        logger.error(f"Auto-fix error: {e}")
        return False, f"Auto-fix error: {e}"


def build_escalation_message(escalation: EscalationContext) -> str:
    """Build a rich escalation message for Richard."""
    tz = pytz.timezone(TIMEZONE)

    # Severity emoji
    severity_emoji = {
        Severity.LOW: "ℹ️",
        Severity.MEDIUM: "⚠️",
        Severity.HIGH: "🚨",
        Severity.CRITICAL: "🔴"
    }

    # Type emoji
    type_emoji = {
        EscalationType.DEPLOY_FAILURE: "🚀",
        EscalationType.BUILD_ERROR: "🔨",
        EscalationType.SITE_DOWN: "🌐",
        EscalationType.API_ERROR: "🔌",
        EscalationType.TASK_FAILURE: "❌",
        EscalationType.SECURITY_ALERT: "🔒",
        EscalationType.COST_ALERT: "💰",
        EscalationType.UNKNOWN: "❓"
    }

    msg = f"{severity_emoji.get(escalation.severity, '❓')} **{escalation.severity.value.upper()} ALERT**\n\n"
    msg += f"{type_emoji.get(escalation.escalation_type, '❓')} **{escalation.title}**\n\n"

    msg += f"**Description:** {escalation.description}\n"

    if escalation.affected_project:
        msg += f"**Project:** {escalation.affected_project}\n"

    if escalation.affected_url:
        msg += f"**URL:** {escalation.affected_url}\n"

    if escalation.error_details:
        details = escalation.error_details[:500]
        msg += f"\n**Error Details:**\n```\n{details}\n```\n"

    if escalation.auto_fix_attempts > 0:
        msg += f"\n**Auto-Fix Attempts:** {escalation.auto_fix_attempts}\n"
        for i, result in enumerate(escalation.auto_fix_results[-2:], 1):  # Last 2 attempts
            msg += f"_Attempt {i}:_ {result[:100]}...\n"

    if escalation.suggested_actions:
        msg += f"\n**Suggested Actions:**\n"
        for action in escalation.suggested_actions[:3]:
            msg += f"• {action}\n"

    msg += f"\n_Time: {escalation.timestamp.strftime('%H:%M %Z')}_"

    return msg


async def handle_error(
    error_text: str,
    context: Optional[str] = None,
    project: Optional[str] = None,
    url: Optional[str] = None,
    send_callback: Optional[Callable] = None,
    auto_fix: bool = True
) -> EscalationContext:
    """
    Handle an error - try to fix, then escalate if needed.

    Args:
        error_text: The error message
        context: Additional context
        project: Affected project name
        url: Affected URL
        send_callback: Function to send messages to Richard
        auto_fix: Whether to attempt auto-fix

    Returns:
        EscalationContext with results
    """
    # Classify the error
    error_type, severity = classify_error(error_text, context)

    # Build escalation context
    escalation = EscalationContext(
        escalation_type=error_type,
        severity=severity,
        title=error_text[:100],
        description=context or error_text[:200],
        error_details=error_text,
        affected_project=project,
        affected_url=url
    )

    # Generate suggested actions
    escalation.suggested_actions = _generate_suggestions(escalation)

    # For low severity, just log it
    if severity == Severity.LOW:
        _log_escalation(escalation)
        return escalation

    # For critical, escalate immediately
    if severity == Severity.CRITICAL:
        if send_callback and _should_escalate(escalation):
            escalation.escalated = True
            await send_callback(build_escalation_message(escalation))
            _recent_escalations[_get_escalation_key(escalation)] = escalation.timestamp
        _log_escalation(escalation)
        return escalation

    # For medium/high, try auto-fix first
    if auto_fix and severity in [Severity.MEDIUM, Severity.HIGH]:
        if send_callback:
            await send_callback(f"🔧 Issue detected: {error_text[:100]}... Attempting auto-fix...")

        fixed, result = await try_auto_fix(escalation)

        if fixed:
            if send_callback:
                await send_callback(f"✅ **Auto-fixed:** {escalation.title}\n\n{result[:300]}")
            _log_escalation(escalation)
            return escalation

    # Auto-fix failed or not attempted - escalate
    if send_callback and _should_escalate(escalation):
        escalation.escalated = True
        await send_callback(build_escalation_message(escalation))
        _recent_escalations[_get_escalation_key(escalation)] = escalation.timestamp

    _log_escalation(escalation)
    return escalation


def _generate_suggestions(escalation: EscalationContext) -> List[str]:
    """Generate suggested actions based on error type."""
    suggestions = {
        EscalationType.DEPLOY_FAILURE: [
            "Check Vercel dashboard for build logs",
            "Run 'npm run build' locally to see errors",
            "Try rollback with /rollback <project>"
        ],
        EscalationType.BUILD_ERROR: [
            "Check the error line number",
            "Look for missing imports or typos",
            "Run 'npm install' if dependencies missing"
        ],
        EscalationType.SITE_DOWN: [
            "Check Vercel status page",
            "Verify DNS settings",
            "Check for recent deployments that might have broken it"
        ],
        EscalationType.API_ERROR: [
            "Check API keys in .env.local",
            "Check service status (Anthropic, Supabase, etc.)",
            "Review API usage/quotas"
        ],
        EscalationType.SECURITY_ALERT: [
            "Review access logs",
            "Check for unauthorized changes",
            "Rotate affected credentials"
        ],
        EscalationType.COST_ALERT: [
            "Check API usage dashboard",
            "Review recent high-usage tasks",
            "Consider rate limiting"
        ]
    }

    return suggestions.get(escalation.escalation_type, [
        "Review the error details",
        "Check recent changes",
        "Try the operation again"
    ])


def _log_escalation(escalation: EscalationContext) -> None:
    """Log an escalation to history."""
    _escalation_history.append(escalation)

    # Keep only last 100
    if len(_escalation_history) > 100:
        _escalation_history.pop(0)

    # Save to file
    try:
        log_data = []
        for e in _escalation_history[-50:]:  # Save last 50
            log_data.append({
                "type": e.escalation_type.value,
                "severity": e.severity.value,
                "title": e.title,
                "project": e.affected_project,
                "escalated": e.escalated,
                "resolved": e.resolved,
                "timestamp": e.timestamp.isoformat()
            })

        with open(ESCALATION_LOG_FILE, "w") as f:
            json.dump(log_data, f, indent=2)

    except Exception as e:
        logger.error(f"Error logging escalation: {e}")


def get_escalation_stats() -> Dict:
    """Get escalation statistics."""
    total = len(_escalation_history)
    if total == 0:
        return {"total": 0}

    escalated = sum(1 for e in _escalation_history if e.escalated)
    resolved = sum(1 for e in _escalation_history if e.resolved)
    auto_fixed = sum(1 for e in _escalation_history if e.resolved and e.auto_fix_attempts > 0)

    by_type = {}
    for e in _escalation_history:
        t = e.escalation_type.value
        by_type[t] = by_type.get(t, 0) + 1

    return {
        "total": total,
        "escalated": escalated,
        "resolved": resolved,
        "auto_fixed": auto_fixed,
        "by_type": by_type,
        "auto_fix_rate": f"{(auto_fixed/total*100):.1f}%" if total > 0 else "0%"
    }


def get_recent_escalations(limit: int = 10) -> List[Dict]:
    """Get recent escalations."""
    return [
        {
            "type": e.escalation_type.value,
            "severity": e.severity.value,
            "title": e.title[:50],
            "project": e.affected_project,
            "escalated": e.escalated,
            "resolved": e.resolved,
            "timestamp": e.timestamp.isoformat()
        }
        for e in _escalation_history[-limit:]
    ]
