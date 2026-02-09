"""
Kiyomi — Webhook Handler
External services POST to Kiyomi's HTTP server to trigger AI actions.

GitHub push → "Summarize what changed"
Stripe payment → "New payment received from [customer]"
Custom script → "Build finished, deploy to production"

Each webhook has an action template with {payload} placeholder.
When triggered, Kiyomi substitutes the payload, runs it through AI, sends result to Telegram.
"""
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from engine.config import CONFIG_DIR

logger = logging.getLogger("kiyomi.webhooks")

WEBHOOKS_FILE = CONFIG_DIR / "webhooks.json"


# ── Persistence ──────────────────────────────────────────────

def _load_webhooks() -> list[dict]:
    """Load all webhooks from disk."""
    if WEBHOOKS_FILE.exists():
        try:
            with open(WEBHOOKS_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load webhooks.json: {e}")
    return []


def _save_webhooks(webhooks: list[dict]):
    """Save all webhooks to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(WEBHOOKS_FILE, "w") as f:
        json.dump(webhooks, f, indent=2)


# ── CRUD ─────────────────────────────────────────────────────

def create_webhook(name: str, action_template: str, secret: Optional[str] = None) -> dict:
    """Create a new webhook.

    Args:
        name: Human-readable name (e.g. "GitHub Push")
        action_template: Prompt template with {payload} placeholder
        secret: Optional HMAC secret for payload validation

    Returns the created webhook entry with its ID.
    """
    hook_id = f"hook_{uuid.uuid4().hex[:10]}"
    now = datetime.now()

    entry = {
        "id": hook_id,
        "name": name,
        "action": action_template,
        "secret": secret,
        "active": True,
        "created": now.isoformat(timespec="seconds"),
        "last_triggered": None,
        "trigger_count": 0,
    }

    webhooks = _load_webhooks()
    webhooks.append(entry)
    _save_webhooks(webhooks)

    logger.info(f"Webhook created: {name} ({hook_id})")
    return entry


def delete_webhook(hook_id: str) -> bool:
    """Delete a webhook by ID."""
    webhooks = _load_webhooks()
    new_webhooks = [w for w in webhooks if w["id"] != hook_id]
    if len(new_webhooks) < len(webhooks):
        _save_webhooks(new_webhooks)
        logger.info(f"Webhook deleted: {hook_id}")
        return True
    return False


def deactivate_webhook(hook_id: str) -> bool:
    """Deactivate a webhook (keep it but stop it from firing)."""
    webhooks = _load_webhooks()
    for w in webhooks:
        if w["id"] == hook_id:
            w["active"] = False
            _save_webhooks(webhooks)
            logger.info(f"Webhook deactivated: {hook_id}")
            return True
    return False


def list_webhooks() -> list[dict]:
    """Return all active webhooks."""
    return [w for w in _load_webhooks() if w.get("active", True)]


def get_webhook(hook_id: str) -> Optional[dict]:
    """Get a specific webhook by ID."""
    for w in _load_webhooks():
        if w["id"] == hook_id:
            return w
    return None


# ── Webhook Processing ───────────────────────────────────────

def validate_signature(hook: dict, payload_bytes: bytes, signature: str) -> bool:
    """Validate HMAC-SHA256 signature if the webhook has a secret.

    The signature should be in the format: sha256=<hex_digest>
    Compatible with GitHub webhook signatures.

    Returns True if valid (or if no secret is configured).
    """
    secret = hook.get("secret")
    if not secret:
        return True  # No secret = no validation required

    if not signature:
        return False

    # Strip "sha256=" prefix if present
    if signature.startswith("sha256="):
        signature = signature[7:]

    expected = hmac.HMAC(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


def handle_webhook(hook_id: str, payload: str, signature: Optional[str] = None) -> Optional[str]:
    """Process an incoming webhook and return the AI prompt to execute.

    Args:
        hook_id: The webhook ID from the URL
        payload: The raw payload body (string)
        signature: Optional HMAC signature header

    Returns:
        The action prompt with {payload} substituted, or None if invalid.
    """
    hook = get_webhook(hook_id)
    if not hook:
        logger.warning(f"Webhook not found: {hook_id}")
        return None

    if not hook.get("active", True):
        logger.warning(f"Webhook inactive: {hook_id}")
        return None

    # Validate signature if secret is set
    if hook.get("secret"):
        if not validate_signature(hook, payload.encode("utf-8"), signature or ""):
            logger.warning(f"Webhook signature validation failed: {hook_id}")
            return None

    # Truncate very large payloads to avoid overwhelming AI
    truncated_payload = payload[:5000]
    if len(payload) > 5000:
        truncated_payload += f"\n\n[Payload truncated — original was {len(payload)} chars]"

    # Substitute payload into action template
    action = hook.get("action", "Process this webhook payload: {payload}")
    prompt = action.replace("{payload}", truncated_payload)

    # Update trigger stats
    _mark_triggered(hook_id)

    logger.info(f"Webhook triggered: {hook.get('name', hook_id)}")
    return prompt


def _mark_triggered(hook_id: str):
    """Update last_triggered and trigger_count."""
    webhooks = _load_webhooks()
    for w in webhooks:
        if w["id"] == hook_id:
            w["last_triggered"] = datetime.now().isoformat(timespec="seconds")
            w["trigger_count"] = w.get("trigger_count", 0) + 1
            break
    _save_webhooks(webhooks)
