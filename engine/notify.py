"""
Kiyomi — macOS Native Notifications
Send system notification banners via osascript. Zero dependencies.
Falls back gracefully on non-macOS systems.
"""
import logging
import platform
import subprocess

logger = logging.getLogger("kiyomi.notify")

IS_MACOS = platform.system() == "Darwin"


def send_notification(title: str, message: str, sound: bool = True) -> bool:
    """Send a native macOS notification banner.

    Returns True if the notification was sent successfully, False otherwise.
    On non-macOS systems this is a silent no-op.
    """
    if not IS_MACOS:
        logger.debug("Notifications only supported on macOS")
        return False

    try:
        # AppleScript uses double-quoted strings; escape backslashes and double quotes
        safe_message = message.replace("\\", "\\\\").replace('"', '\\"')
        safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
        sound_str = 'sound name "default"' if sound else ""
        script = (
            f'display notification "{safe_message}" '
            f'with title "{safe_title}" {sound_str}'
        )
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=5,
        )
        if result.returncode == 0:
            logger.debug(f"Notification sent: {title}")
            return True
        else:
            logger.warning(f"osascript failed: {result.stderr.decode()[:200]}")
            return False
    except FileNotFoundError:
        logger.warning("osascript not found — notifications unavailable")
        return False
    except subprocess.TimeoutExpired:
        logger.warning("osascript timed out")
        return False
    except Exception as e:
        logger.error(f"Notification error: {e}")
        return False
