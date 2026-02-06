"""
Kiyomi Self-Update System
Checks GitHub Releases for new versions and auto-updates.
No git dependency — works on any Mac.
"""
import asyncio
import json
import logging
import os
import re
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

# GitHub repo for update checks
GITHUB_OWNER = "RichardEchols"
GITHUB_REPO = "kiyomi"
RELEASES_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"

# Where Kiyomi lives on disk
INSTALL_DIR = Path.home() / ".kiyomi"
APP_DIR = INSTALL_DIR / "app"
VERSION_FILE = Path(__file__).parent / "VERSION"


def is_update_request(message: str) -> bool:
    """Detect if user is asking to update Kiyomi herself."""
    message_lower = message.lower().strip()

    update_patterns = [
        r'\bupdate\s*(yourself|kiyomi)\b',
        r'\bupgrade\s*(yourself|kiyomi)\b',
        r'\bcheck\s+for\s+updates?\b',
        r'\bget\s+latest\s+version\b',
        r'\bupdate\s+to\s+latest\b',
        r'\bupgrade\s+to\s+latest\b',
        r'\bplease\s+update\b',
        r'\bplease\s+upgrade\b',
        r'^update$',
        r'^upgrade$',
    ]

    for pattern in update_patterns:
        if re.search(pattern, message_lower):
            return True

    # Check for standalone "update" but exclude false positives
    if 'update' in message_lower:
        false_positives = [
            'calendar', 'spreadsheet', 'document', 'profile', 'status',
            'schedule', 'appointment', 'meeting', 'reminder', 'task',
            'file', 'record', 'database', 'contact', 'address',
        ]
        for fp in false_positives:
            if fp in message_lower:
                return False

        update_indicators = ['update me', 'update us', 'need an update', 'want an update']
        for indicator in update_indicators:
            if indicator in message_lower:
                return True

    return False


def get_current_version() -> str:
    """Get current version from VERSION file."""
    try:
        if VERSION_FILE.exists():
            return VERSION_FILE.read_text().strip()
    except Exception as e:
        logger.warning(f"Could not read VERSION file: {e}")
    return "unknown"


def _parse_version(version_str: str) -> tuple:
    """Parse 'x.y.z' into a comparable tuple."""
    try:
        parts = version_str.strip().lstrip("v").split(".")
        return tuple(int(p) for p in parts)
    except (ValueError, AttributeError):
        return (0, 0, 0)


async def check_for_updates() -> dict:
    """Check GitHub Releases for a newer version.

    Returns:
        Dictionary with keys: available, current, latest, changes, download_url
    """
    current = get_current_version()

    try:
        req = urllib.request.Request(
            RELEASES_URL,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "Kiyomi-Updater"},
        )

        loop = asyncio.get_event_loop()
        response_data = await loop.run_in_executor(
            None, lambda: urllib.request.urlopen(req, timeout=15).read()
        )
        release = json.loads(response_data)

        latest_tag = release.get("tag_name", "")
        latest_version = latest_tag.lstrip("v")
        body = release.get("body", "No changelog provided.")

        # Find the zip asset
        download_url = ""
        for asset in release.get("assets", []):
            if asset["name"].endswith(".zip"):
                download_url = asset["browser_download_url"]
                break

        # Compare versions
        current_tuple = _parse_version(current)
        latest_tuple = _parse_version(latest_version)
        updates_available = latest_tuple > current_tuple

        if updates_available:
            logger.info(f"Update available: {current} -> {latest_version}")
        else:
            logger.info(f"Up to date: {current}")

        return {
            "available": updates_available,
            "current": current,
            "latest": latest_version,
            "changes": body,
            "download_url": download_url,
        }

    except Exception as e:
        logger.error(f"Update check failed: {e}")
        return {
            "available": False,
            "current": current,
            "latest": "unknown",
            "changes": f"Update check failed: {str(e)}",
            "download_url": "",
        }


async def perform_update() -> dict:
    """Download and install the latest version from GitHub Releases.

    Returns:
        Dictionary with keys: success, message, changes
    """
    try:
        update_info = await check_for_updates()

        if not update_info["available"]:
            return {
                "success": True,
                "message": f"Already on the latest version ({update_info['current']})",
                "changes": "",
            }

        download_url = update_info.get("download_url", "")
        if not download_url:
            return {
                "success": False,
                "message": "No download available for this release.",
                "changes": "",
            }

        current_version = update_info["current"]
        new_version = update_info["latest"]

        logger.info(f"Downloading update {new_version} from {download_url}...")

        # Download zip to temp file
        loop = asyncio.get_event_loop()

        def _download():
            req = urllib.request.Request(
                download_url,
                headers={"User-Agent": "Kiyomi-Updater"},
            )
            tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
            with urllib.request.urlopen(req, timeout=120) as resp:
                shutil.copyfileobj(resp, tmp)
            tmp.close()
            return tmp.name

        zip_path = await loop.run_in_executor(None, _download)

        logger.info(f"Downloaded to {zip_path}, extracting...")

        # Extract to temp dir first
        tmp_extract = tempfile.mkdtemp(prefix="kiyomi-update-")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp_extract)

        # Find the app directory inside the zip (may be nested)
        extracted_items = os.listdir(tmp_extract)
        source_dir = Path(tmp_extract)
        if len(extracted_items) == 1 and (source_dir / extracted_items[0]).is_dir():
            source_dir = source_dir / extracted_items[0]

        # Backup current app
        backup_dir = INSTALL_DIR / "app.backup"
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        if APP_DIR.exists():
            shutil.copytree(APP_DIR, backup_dir)

        # Replace app files
        if APP_DIR.exists():
            shutil.rmtree(APP_DIR)
        shutil.copytree(source_dir, APP_DIR)

        # Clean up
        os.unlink(zip_path)
        shutil.rmtree(tmp_extract, ignore_errors=True)

        # Check if requirements changed
        new_req = APP_DIR / "requirements.txt"
        if new_req.exists():
            try:
                import subprocess
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-q", "-r", str(new_req)],
                    capture_output=True,
                    timeout=120,
                )
                logger.info("Dependencies updated")
            except Exception as e:
                logger.warning(f"Dependency update failed (non-fatal): {e}")

        logger.info(f"Update complete: {current_version} -> {new_version}")

        return {
            "success": True,
            "message": f"Updated from {current_version} to {new_version}",
            "changes": update_info.get("changes", ""),
        }

    except Exception as e:
        logger.error(f"Update failed: {e}")
        # Try to restore backup
        backup_dir = INSTALL_DIR / "app.backup"
        if backup_dir.exists() and not APP_DIR.exists():
            try:
                shutil.copytree(backup_dir, APP_DIR)
                logger.info("Restored from backup after failed update")
            except Exception:
                pass
        return {
            "success": False,
            "message": f"Update failed: {str(e)}",
            "changes": "",
        }


async def restart_bot():
    """Restart the Kiyomi bot process."""
    try:
        logger.info("Restarting bot process...")
        executable = sys.executable
        args = sys.argv.copy()
        if args and not args[0].endswith(('python', 'python3', 'Kiyomi')):
            args.insert(0, executable)
        logger.info(f"Restarting with: {executable} {args}")
        os.execv(executable, args)
    except Exception as e:
        logger.error(f"Failed to restart bot: {e}")
        try:
            import subprocess
            subprocess.Popen([sys.executable] + sys.argv)
            sys.exit(0)
        except Exception as fallback_error:
            logger.error(f"Subprocess restart also failed: {fallback_error}")
            raise RuntimeError(f"Could not restart bot: {e}")


if __name__ == "__main__":
    print(f"Current version: {get_current_version()}")

    test_cases = [
        ("update", True),
        ("update yourself", True),
        ("check for updates", True),
        ("upgrade", True),
        ("update my calendar", False),
        ("update Kiyomi", True),
    ]

    print("\nTesting is_update_request:")
    for message, expected in test_cases:
        result = is_update_request(message)
        status = "PASS" if result == expected else "FAIL"
        print(f"  {status}: '{message}' -> {result} (expected {expected})")

    async def test_async():
        print("\nChecking for updates...")
        result = await check_for_updates()
        print(f"  Result: {result}")

    asyncio.run(test_async())
