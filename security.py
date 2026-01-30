"""
Kiyomi Security - User validation and command filtering
"""
import re
from typing import Optional
from config import ALLOWED_USER_IDS, ALLOWED_DIRECTORIES

# ============================================
# BLOCKED PATTERNS (Never execute)
# ============================================
BLOCKED_PATTERNS = [
    r"sudo\s",
    r"rm\s+-rf\s+[/~]",
    r"rm\s+-rf\s+\*",
    r"chmod\s+777",
    r"curl.*\|\s*sh",
    r"wget.*\|\s*sh",
    r"~\/\.ssh",
    r"~\/\.zshrc",
    r"~\/\.bash_profile",
    r"\/etc\/",
    r"\/System\/",
    r"\/Library\/",
    r"mkfs\.",
    r"dd\s+if=",
    r":(){",  # Fork bomb
    r">\s*/dev/sd",
]

# ============================================
# CONFIRMATION PATTERNS (Ask before executing)
# ============================================
CONFIRM_PATTERNS = [
    r"git\s+push.*--force",
    r"rm\s+.*-r",
    r"DROP\s+TABLE",
    r"npm\s+install\s+-g",
    r"brew\s+install",
    # Note: Removed overly broad patterns:
    # - "delete" matched any text containing delete
    # - "pip install" was annoying for normal dev work
    # - vercel --prod removed - Richard doesn't want deploy confirmations
]


def is_authorized(user_id: int) -> bool:
    """Check if user is in the allowlist."""
    return user_id in ALLOWED_USER_IDS


def contains_blocked_pattern(text: str) -> Optional[str]:
    """
    Check if text contains any blocked patterns.
    Returns the matched pattern if found, None otherwise.
    """
    if not text:
        return None

    text_lower = text.lower()
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return pattern
    return None


def needs_confirmation(text: str) -> Optional[str]:
    """
    Check if text contains patterns that need confirmation.
    Returns the matched pattern if found, None otherwise.
    """
    if not text:
        return None

    text_lower = text.lower()
    for pattern in CONFIRM_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return pattern
    return None


def is_path_allowed(path: str) -> bool:
    """Check if a path is within allowed directories.

    Uses os.path.realpath to resolve symlinks and prevent path traversal attacks.
    """
    if not path:
        return False

    import os
    # Resolve symlinks and normalize to prevent traversal via ../
    normalized = os.path.realpath(os.path.expanduser(path))

    for allowed_dir in ALLOWED_DIRECTORIES:
        real_allowed = os.path.realpath(allowed_dir)
        # Use os.path.commonpath for robust prefix checking
        try:
            common = os.path.commonpath([normalized, real_allowed])
            if common == real_allowed:
                return True
        except ValueError:
            # Different drives on Windows, skip
            continue
    return False


def sanitize_for_logging(text: str) -> str:
    """Remove sensitive info from text for logging."""
    # Mask potential tokens/keys
    sanitized = re.sub(r'[A-Za-z0-9_-]{30,}', '[REDACTED]', text)
    # Mask phone numbers
    sanitized = re.sub(r'\+?1?\d{10,}', '[PHONE]', sanitized)
    # Mask emails
    sanitized = re.sub(r'[\w.+-]+@[\w-]+\.[\w.-]+', '[EMAIL]', sanitized)
    return sanitized
