"""
Kiyomi Git Tools - Git operations for version control

This module provides:
- Auto-commit with good messages
- Push to remote
- Rollback capability
- Status checking
"""
import asyncio
import subprocess
import logging
import re
from pathlib import Path
from typing import Tuple, Optional, List
from datetime import datetime

from projects import Project

logger = logging.getLogger(__name__)


# ============================================
# GIT STATUS
# ============================================

async def git_status(project: Project) -> Tuple[bool, str]:
    """
    Get git status for a project.

    Returns:
        Tuple of (success, status_output)
    """
    if not Path(project.path).exists():
        return False, f"Project path not found: {project.path}"

    git_dir = Path(project.path) / ".git"
    if not git_dir.exists():
        return False, "Not a git repository"

    try:
        process = await asyncio.create_subprocess_exec(
            "git", "status", "--short",
            cwd=project.path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=10
        )

        output = stdout.decode("utf-8", errors="replace")
        if output.strip():
            return True, output
        else:
            return True, "Working tree clean"

    except Exception as e:
        return False, f"Git status error: {str(e)}"


async def has_uncommitted_changes(project: Project) -> bool:
    """Check if project has uncommitted changes."""
    success, output = await git_status(project)
    if not success:
        return False
    return output != "Working tree clean"


# ============================================
# GIT COMMIT
# ============================================

async def git_add_all(project: Project) -> Tuple[bool, str]:
    """Stage all changes."""
    try:
        process = await asyncio.create_subprocess_exec(
            "git", "add", "-A",
            cwd=project.path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=10
        )

        if process.returncode == 0:
            return True, "Changes staged"
        else:
            return False, stderr.decode("utf-8", errors="replace")

    except Exception as e:
        return False, f"Git add error: {str(e)}"


async def git_commit(project: Project, message: str) -> Tuple[bool, str]:
    """
    Create a git commit.

    Args:
        project: Project to commit in
        message: Commit message

    Returns:
        Tuple of (success, output)
    """
    # First stage changes
    add_success, add_output = await git_add_all(project)
    if not add_success:
        return False, f"Failed to stage changes: {add_output}"

    try:
        process = await asyncio.create_subprocess_exec(
            "git", "commit", "-m", message,
            cwd=project.path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=30
        )

        output = stdout.decode("utf-8", errors="replace")
        errors = stderr.decode("utf-8", errors="replace")

        if process.returncode == 0:
            logger.info(f"Committed in {project.name}: {message}")
            return True, f"Committed: {message}"
        else:
            # Check if just nothing to commit
            if "nothing to commit" in errors or "nothing to commit" in output:
                return True, "Nothing to commit"
            return False, f"Commit failed: {errors or output}"

    except Exception as e:
        return False, f"Git commit error: {str(e)}"


def generate_commit_message(changes_description: str) -> str:
    """
    Generate a good commit message from a description of changes.

    Args:
        changes_description: What was changed

    Returns:
        Formatted commit message
    """
    # Clean up the description
    desc = changes_description.strip()

    # Truncate if too long
    if len(desc) > 72:
        desc = desc[:69] + "..."

    # Capitalize first letter
    if desc and desc[0].islower():
        desc = desc[0].upper() + desc[1:]

    # Add conventional commit prefix if not present
    prefixes = ["fix:", "feat:", "chore:", "docs:", "style:", "refactor:", "test:"]
    has_prefix = any(desc.lower().startswith(p) for p in prefixes)

    if not has_prefix:
        # Try to detect the type
        desc_lower = desc.lower()
        if any(word in desc_lower for word in ["fix", "bug", "error", "issue"]):
            desc = f"fix: {desc}"
        elif any(word in desc_lower for word in ["add", "new", "create"]):
            desc = f"feat: {desc}"
        elif any(word in desc_lower for word in ["update", "change", "modify"]):
            desc = f"chore: {desc}"
        else:
            desc = f"chore: {desc}"

    return desc


async def smart_commit(project: Project, description: str) -> Tuple[bool, str]:
    """
    Smart commit with auto-generated message.

    Args:
        project: Project to commit in
        description: Description of what was changed

    Returns:
        Tuple of (success, output)
    """
    message = generate_commit_message(description)
    return await git_commit(project, message)


# ============================================
# GIT PUSH
# ============================================

async def git_push(project: Project, force: bool = False) -> Tuple[bool, str]:
    """
    Push commits to remote.

    Args:
        project: Project to push
        force: Use --force flag (careful!)

    Returns:
        Tuple of (success, output)
    """
    cmd = ["git", "push"]
    if force:
        cmd.append("--force")

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=project.path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=60
        )

        output = stdout.decode("utf-8", errors="replace")
        errors = stderr.decode("utf-8", errors="replace")

        if process.returncode == 0:
            logger.info(f"Pushed {project.name}")
            return True, "Pushed to remote"
        else:
            return False, f"Push failed: {errors or output}"

    except Exception as e:
        return False, f"Git push error: {str(e)}"


# ============================================
# GIT ROLLBACK
# ============================================

async def git_log(project: Project, count: int = 5) -> Tuple[bool, List[dict]]:
    """
    Get recent commits.

    Returns:
        Tuple of (success, list of commit dicts)
    """
    try:
        process = await asyncio.create_subprocess_exec(
            "git", "log", f"-{count}", "--oneline", "--format=%H|%s|%cr",
            cwd=project.path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=10
        )

        output = stdout.decode("utf-8", errors="replace")
        commits = []

        for line in output.strip().split("\n"):
            if line:
                parts = line.split("|")
                if len(parts) >= 3:
                    commits.append({
                        "hash": parts[0],
                        "message": parts[1],
                        "time": parts[2]
                    })

        return True, commits

    except Exception as e:
        return False, []


async def git_revert_last(project: Project) -> Tuple[bool, str]:
    """
    Revert the last commit.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            "git", "revert", "HEAD", "--no-edit",
            cwd=project.path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=30
        )

        if process.returncode == 0:
            return True, "Reverted last commit"
        else:
            errors = stderr.decode("utf-8", errors="replace")
            return False, f"Revert failed: {errors}"

    except Exception as e:
        return False, f"Git revert error: {str(e)}"


async def git_reset_hard(project: Project, commit: str = "HEAD~1") -> Tuple[bool, str]:
    """
    Hard reset to a commit (DANGEROUS - loses changes).

    Only use when explicitly requested.
    """
    logger.warning(f"Hard reset requested for {project.name} to {commit}")

    try:
        process = await asyncio.create_subprocess_exec(
            "git", "reset", "--hard", commit,
            cwd=project.path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=10
        )

        if process.returncode == 0:
            return True, f"Reset to {commit}"
        else:
            errors = stderr.decode("utf-8", errors="replace")
            return False, f"Reset failed: {errors}"

    except Exception as e:
        return False, f"Git reset error: {str(e)}"


# ============================================
# COMMIT AFTER FIX
# ============================================

async def commit_fix(project: Project, fix_description: str, push: bool = True) -> Tuple[bool, str]:
    """
    Full workflow: stage, commit, optionally push.

    Args:
        project: Project that was fixed
        fix_description: What was fixed
        push: Whether to push after commit

    Returns:
        Tuple of (success, message)
    """
    # Check if there are changes
    has_changes = await has_uncommitted_changes(project)
    if not has_changes:
        return True, "No changes to commit"

    # Commit
    commit_success, commit_msg = await smart_commit(project, fix_description)
    if not commit_success:
        return False, commit_msg

    # Push if requested
    if push:
        push_success, push_msg = await git_push(project)
        if not push_success:
            return True, f"Committed but push failed: {push_msg}"
        return True, f"Committed and pushed: {fix_description}"

    return True, f"Committed: {fix_description}"


# ============================================
# GIT BRANCH
# ============================================

async def get_current_branch(project: Project) -> Optional[str]:
    """Get the current git branch."""
    try:
        process = await asyncio.create_subprocess_exec(
            "git", "branch", "--show-current",
            cwd=project.path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, _ = await asyncio.wait_for(
            process.communicate(),
            timeout=10
        )

        return stdout.decode("utf-8", errors="replace").strip()

    except:
        return None
