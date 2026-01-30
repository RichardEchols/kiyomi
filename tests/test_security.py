"""Tests for security module."""

import os
import sys
import tempfile
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_is_path_allowed_basic():
    """Test basic path checking."""
    from security import is_path_allowed

    # Allowed paths (within home dirs)
    home = str(Path.home())
    assert is_path_allowed(f"{home}/Documents/test.txt") is True
    assert is_path_allowed(f"{home}/Desktop/file.py") is True

    # Disallowed paths
    assert is_path_allowed("/etc/passwd") is False
    assert is_path_allowed("/usr/local/bin/something") is False
    assert is_path_allowed("") is False
    assert is_path_allowed(None) is False


def test_is_path_allowed_traversal():
    """Test path traversal prevention."""
    from security import is_path_allowed

    home = str(Path.home())

    # Traversal attempts should be caught
    assert is_path_allowed(f"{home}/Documents/../../../etc/passwd") is False
    assert is_path_allowed(f"{home}/Documents/./../../etc/shadow") is False


def test_is_path_allowed_symlink():
    """Test symlink resolution."""
    from security import is_path_allowed

    # Create a temp symlink pointing outside allowed dirs
    with tempfile.TemporaryDirectory() as tmpdir:
        # This temp dir is NOT in allowed dirs
        link_path = os.path.join(str(Path.home()), "Documents", "_test_symlink")
        try:
            os.symlink(tmpdir, link_path)
            # The symlink resolves to tmpdir which is NOT in allowed dirs
            assert is_path_allowed(link_path) is False
        finally:
            try:
                os.unlink(link_path)
            except OSError:
                pass


def test_sanitize_for_logging():
    """Test sensitive data scrubbing."""
    from security import sanitize_for_logging

    # Should redact long tokens
    text = "Bearer sk_live_1234567890abcdefghijklmnopqrstuvwxyz"
    result = sanitize_for_logging(text)
    assert "sk_live_" not in result
    assert "[REDACTED]" in result

    # Should redact emails
    text = "Contact user@example.com for help"
    result = sanitize_for_logging(text)
    assert "user@example.com" not in result
    assert "[EMAIL]" in result

    # Should redact phone numbers
    text = "Call 14045551234"
    result = sanitize_for_logging(text)
    assert "14045551234" not in result


def test_contains_blocked_pattern():
    """Test dangerous command detection."""
    from security import contains_blocked_pattern

    # These should be blocked
    assert contains_blocked_pattern("rm -rf /") is not None
    assert contains_blocked_pattern("sudo su") is not None

    # These should be allowed
    assert contains_blocked_pattern("ls -la") is None
    assert contains_blocked_pattern("git status") is None
    assert contains_blocked_pattern("npm install") is None


if __name__ == "__main__":
    test_is_path_allowed_basic()
    print("PASS: test_is_path_allowed_basic")

    test_is_path_allowed_traversal()
    print("PASS: test_is_path_allowed_traversal")

    test_is_path_allowed_symlink()
    print("PASS: test_is_path_allowed_symlink")

    test_sanitize_for_logging()
    print("PASS: test_sanitize_for_logging")

    test_contains_blocked_pattern()
    print("PASS: test_contains_blocked_pattern")

    print("\nAll security tests passed!")
