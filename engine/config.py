"""
Kiyomi v5.0 — Simple Configuration
All config lives in ~/.kiyomi/config.json
"""
import json
import logging
from pathlib import Path

CONFIG_DIR = Path.home() / ".kiyomi"
CONFIG_FILE = CONFIG_DIR / "config.json"
IDENTITY_FILE = CONFIG_DIR / "identity.md"
WORKSPACE = CONFIG_DIR  # CLI cwd — identity files live here
LOGS_DIR = CONFIG_DIR / "logs"

# Defaults
DEFAULT_CONFIG = {
    "name": "",
    "cli": "",  # "claude", "codex", or "gemini"
    "telegram_token": "",
    "telegram_user_id": "",
    "timezone": "America/New_York",
    "model": "",  # optional model override
    "cli_timeout": 120,  # timeout for CLI calls in seconds
    "setup_complete": False,
    "auto_update": False,
}


def ensure_dirs():
    """Create all required directories."""
    for d in [CONFIG_DIR, LOGS_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    """Load config from ~/.kiyomi/config.json."""
    ensure_dirs()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                stored = json.load(f)
                return {**DEFAULT_CONFIG, **stored}
        except (json.JSONDecodeError, IOError) as e:
            logging.getLogger(__name__).error(f"Failed to load config.json: {e}")
    return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    """Save config to ~/.kiyomi/config.json."""
    ensure_dirs()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
