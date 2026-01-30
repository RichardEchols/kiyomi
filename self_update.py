"""
Kiyomi Self-Update System - Modify own code safely

Features:
- Parse update requests
- Validate syntax before applying
- Backup current code
- Apply changes
- Auto-restart after updates
"""
import asyncio
import logging
import shutil
import ast
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List, Dict

import pytz
from config import BASE_DIR, TIMEZONE

logger = logging.getLogger(__name__)

# Self-update configuration
BACKUP_DIR = BASE_DIR / "backups"
UPDATE_LOG_FILE = BASE_DIR / "update_log.json"
KEIKO_FILES = [
    "bot.py",
    "executor.py",
    "config.py",
    "security.py",
    "memory_manager.py",
    "learning.py",
    "reminders.py",
    "skills.py",
    "proactive.py",
    "web_tools.py",
    "heartbeat.py",
    "projects.py",
    "milestones.py",
    "session_state.py",
    "deploy_tools.py",
    "git_tools.py",
    "monitoring.py",
    "voice.py",
    "swarm.py",
    "self_update.py",
    "escalation.py",
    "corrections.py",
    "cost_tracking.py",
]

# Files that are critical and need extra care
CRITICAL_FILES = ["bot.py", "executor.py", "config.py", "security.py"]


def validate_python_syntax(code: str) -> Tuple[bool, Optional[str]]:
    """
    Validate Python syntax.
    Returns (is_valid, error_message).
    """
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, f"Syntax error at line {e.lineno}: {e.msg}"


def validate_file_syntax(file_path: Path) -> Tuple[bool, Optional[str]]:
    """Validate syntax of a Python file."""
    try:
        content = file_path.read_text()
        return validate_python_syntax(content)
    except Exception as e:
        return False, f"Error reading file: {e}"


def backup_file(file_path: Path) -> Optional[Path]:
    """
    Create a backup of a file.
    Returns backup path or None on failure.
    """
    try:
        tz = pytz.timezone(TIMEZONE)
        timestamp = datetime.now(tz).strftime("%Y%m%d_%H%M%S")

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
        backup_path = BACKUP_DIR / backup_name

        shutil.copy2(file_path, backup_path)
        logger.info(f"Backed up {file_path.name} to {backup_path}")

        return backup_path

    except Exception as e:
        logger.error(f"Error backing up file: {e}")
        return None


def restore_from_backup(backup_path: Path, target_path: Path) -> bool:
    """Restore a file from backup."""
    try:
        shutil.copy2(backup_path, target_path)
        logger.info(f"Restored {target_path.name} from backup")
        return True
    except Exception as e:
        logger.error(f"Error restoring backup: {e}")
        return False


def get_recent_backups(file_name: str, limit: int = 5) -> List[Path]:
    """Get recent backups for a file."""
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stem = Path(file_name).stem
        backups = list(BACKUP_DIR.glob(f"{stem}_*"))
        backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return backups[:limit]
    except Exception as e:
        logger.error(f"Error getting backups: {e}")
        return []


async def apply_update(
    file_name: str,
    new_content: str,
    description: str
) -> Tuple[bool, str]:
    """
    Apply an update to a Kiyomi file.

    Args:
        file_name: Name of the file to update
        new_content: New file content
        description: Description of the update

    Returns:
        (success, message)
    """
    # Validate file name
    if file_name not in KEIKO_FILES:
        return False, f"Unknown file: {file_name}. Updatable files: {', '.join(KEIKO_FILES)}"

    file_path = BASE_DIR / file_name

    # Validate syntax
    is_valid, error = validate_python_syntax(new_content)
    if not is_valid:
        return False, f"Invalid syntax: {error}"

    # Create backup
    backup_path = backup_file(file_path)
    if not backup_path:
        return False, "Failed to create backup"

    try:
        # Write new content
        file_path.write_text(new_content)

        # Verify the file is still valid
        is_valid, error = validate_file_syntax(file_path)
        if not is_valid:
            # Restore backup
            restore_from_backup(backup_path, file_path)
            return False, f"Post-write validation failed: {error}"

        # Log update
        _log_update(file_name, description, str(backup_path))

        logger.info(f"Successfully updated {file_name}: {description}")
        return True, f"Updated {file_name}. Backup at {backup_path.name}"

    except Exception as e:
        # Try to restore backup
        if backup_path and backup_path.exists():
            restore_from_backup(backup_path, file_path)
        return False, f"Update failed: {e}"


async def add_function_to_file(
    file_name: str,
    function_code: str,
    description: str
) -> Tuple[bool, str]:
    """
    Add a new function to a file.
    """
    if file_name not in KEIKO_FILES:
        return False, f"Unknown file: {file_name}"

    file_path = BASE_DIR / file_name

    try:
        current_content = file_path.read_text()

        # Validate the function code
        is_valid, error = validate_python_syntax(function_code)
        if not is_valid:
            return False, f"Invalid function syntax: {error}"

        # Append function to file
        new_content = current_content.rstrip() + "\n\n\n" + function_code.strip() + "\n"

        return await apply_update(file_name, new_content, description)

    except Exception as e:
        return False, f"Error adding function: {e}"


async def modify_function(
    file_name: str,
    function_name: str,
    new_function_code: str,
    description: str
) -> Tuple[bool, str]:
    """
    Replace an existing function in a file.
    """
    if file_name not in KEIKO_FILES:
        return False, f"Unknown file: {file_name}"

    file_path = BASE_DIR / file_name

    try:
        current_content = file_path.read_text()

        # Parse the file to find the function
        tree = ast.parse(current_content)

        function_found = False
        function_start = None
        function_end = None

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == function_name:
                    function_found = True
                    function_start = node.lineno - 1  # 0-indexed
                    # Find the end of the function
                    function_end = node.end_lineno if hasattr(node, 'end_lineno') else None
                    break

        if not function_found:
            return False, f"Function '{function_name}' not found in {file_name}"

        if function_end is None:
            return False, "Could not determine function boundaries"

        # Replace the function
        lines = current_content.split('\n')
        new_lines = lines[:function_start] + new_function_code.strip().split('\n') + lines[function_end:]
        new_content = '\n'.join(new_lines)

        return await apply_update(file_name, new_content, description)

    except Exception as e:
        return False, f"Error modifying function: {e}"


def _log_update(file_name: str, description: str, backup_path: str) -> None:
    """Log an update to the update log."""
    import json

    try:
        tz = pytz.timezone(TIMEZONE)
        timestamp = datetime.now(tz).isoformat()

        log_entry = {
            "timestamp": timestamp,
            "file": file_name,
            "description": description,
            "backup": backup_path
        }

        # Load existing log
        if UPDATE_LOG_FILE.exists():
            with open(UPDATE_LOG_FILE) as f:
                log = json.load(f)
        else:
            log = []

        log.append(log_entry)

        # Keep last 100 entries
        log = log[-100:]

        with open(UPDATE_LOG_FILE, "w") as f:
            json.dump(log, f, indent=2)

    except Exception as e:
        logger.error(f"Error logging update: {e}")


def get_update_history(limit: int = 10) -> List[Dict]:
    """Get recent update history."""
    import json

    try:
        if UPDATE_LOG_FILE.exists():
            with open(UPDATE_LOG_FILE) as f:
                log = json.load(f)
            return log[-limit:]
    except Exception as e:
        logger.error(f"Error reading update log: {e}")

    return []


async def restart_keiko() -> Tuple[bool, str]:
    """
    Restart Kiyomi via launchctl.
    This will cause the current process to exit and launchd will restart it.
    """
    try:
        # Use launchctl to restart
        plist_name = "com.kiyomi.telegram-bot"

        # Log the restart
        logger.info("Kiyomi restart requested - reloading via launchctl")

        # First unload, then load
        # We need to do this in a way that allows us to exit gracefully
        restart_script = f"""#!/bin/bash
sleep 2
launchctl unload ~/Library/LaunchAgents/{plist_name}.plist 2>/dev/null
sleep 1
launchctl load ~/Library/LaunchAgents/{plist_name}.plist
"""

        script_path = BASE_DIR / "temp" / "restart.sh"
        script_path.parent.mkdir(exist_ok=True)
        script_path.write_text(restart_script)
        script_path.chmod(0o755)

        # Run the restart script in background (it will survive our exit)
        process = await asyncio.create_subprocess_exec(
            "/bin/bash", str(script_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True  # Detach from parent
        )

        return True, "Restart initiated - Kiyomi will be back in a few seconds"

    except Exception as e:
        logger.error(f"Error initiating restart: {e}")
        return False, f"Restart failed: {e}"


async def process_self_update_request(request: str) -> Tuple[bool, str]:
    """
    Process a natural language self-update request.
    Uses Claude to generate the code changes.
    """
    # Build context about Kiyomi's structure
    context = f"""You are helping update Kiyomi, a Telegram bot assistant.

KEIKO'S FILE STRUCTURE:
{chr(10).join(f'- {f}' for f in KEIKO_FILES)}

CRITICAL FILES (be extra careful):
{chr(10).join(f'- {f}' for f in CRITICAL_FILES)}

CURRENT DIRECTORY: {BASE_DIR}

REQUEST: {request}

If this is a feature addition or modification:
1. Determine which file(s) need to be changed
2. Generate the exact Python code
3. Return in this format:

FILE: <filename>
ACTION: add_function | modify_function | full_replace
FUNCTION_NAME: <name if modifying>
DESCRIPTION: <what this does>
CODE:
```python
<the code>
```

If you cannot safely make this change, explain why."""

    try:
        process = await asyncio.create_subprocess_exec(
            "/Users/richardecholsai2/.local/bin/claude",
            "-p", context,
            "--dangerously-skip-permissions",
            cwd=str(BASE_DIR),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=120)
        response = stdout.decode("utf-8", errors="replace").strip()

        # Parse the response
        import re

        file_match = re.search(r'FILE:\s*(\S+)', response)
        action_match = re.search(r'ACTION:\s*(\S+)', response)
        func_match = re.search(r'FUNCTION_NAME:\s*(\S+)', response)
        desc_match = re.search(r'DESCRIPTION:\s*(.+?)(?=\n(?:CODE|FILE|ACTION)|$)', response, re.DOTALL)
        code_match = re.search(r'```python\n(.*?)```', response, re.DOTALL)

        if not file_match or not code_match:
            return False, f"Could not parse update response. Claude said:\n{response[:500]}"

        file_name = file_match.group(1)
        action = action_match.group(1) if action_match else "add_function"
        func_name = func_match.group(1) if func_match else None
        description = desc_match.group(1).strip() if desc_match else request[:100]
        code = code_match.group(1)

        # Apply the update
        if action == "add_function":
            return await add_function_to_file(file_name, code, description)
        elif action == "modify_function" and func_name:
            return await modify_function(file_name, func_name, code, description)
        elif action == "full_replace":
            return await apply_update(file_name, code, description)
        else:
            return False, f"Unknown action: {action}"

    except asyncio.TimeoutError:
        return False, "Update request timed out"
    except Exception as e:
        logger.error(f"Error processing self-update: {e}")
        return False, f"Error: {e}"


def list_kiyomi_files() -> List[Dict]:
    """List all Kiyomi files with info."""
    files = []
    for file_name in KEIKO_FILES:
        file_path = BASE_DIR / file_name
        if file_path.exists():
            stat = file_path.stat()
            files.append({
                "name": file_name,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "is_critical": file_name in CRITICAL_FILES
            })
        else:
            files.append({
                "name": file_name,
                "exists": False
            })
    return files
