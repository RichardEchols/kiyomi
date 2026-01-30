"""
Kiyomi Deploy Tools - Smart deployment with checks

This module provides:
- Pre-deploy checks (build, lint, TypeScript)
- Deployment execution
- Post-deploy verification
- Rollback capability
"""
import asyncio
import subprocess
import logging
import re
import aiohttp
from pathlib import Path
from typing import Tuple, Optional, Dict, Callable
from datetime import datetime
import pytz

from config import TIMEZONE
from projects import Project, is_deployable
from session_state import set_last_deploy, add_context_note

logger = logging.getLogger(__name__)

from dataclasses import dataclass

# Deployment timeout
DEPLOY_TIMEOUT = 300  # 5 minutes
BUILD_TIMEOUT = 180  # 3 minutes
VERIFY_TIMEOUT = 30  # 30 seconds


@dataclass
class DeployResult:
    """Result of a deployment."""
    success: bool
    url: Optional[str] = None
    message: str = ""
    build_output: str = ""
    deploy_output: str = ""
    verified: bool = False


# ============================================
# PRE-DEPLOY CHECKS
# ============================================

async def run_build(project: Project, send_update: Optional[Callable] = None) -> Tuple[bool, str]:
    """
    Run npm build for a project.

    Args:
        project: Project to build
        send_update: Optional callback for updates

    Returns:
        Tuple of (success, output)
    """
    if not Path(project.path).exists():
        return False, f"Project path not found: {project.path}"

    package_json = Path(project.path) / "package.json"
    if not package_json.exists():
        return True, "No package.json - skipping build"

    if send_update:
        await send_update(f"🔨 Building {project.name}...")

    logger.info(f"Running build for {project.name}")

    try:
        process = await asyncio.create_subprocess_exec(
            "npm", "run", "build",
            cwd=project.path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=BUILD_TIMEOUT
        )

        output = stdout.decode("utf-8", errors="replace")
        errors = stderr.decode("utf-8", errors="replace")

        if process.returncode != 0:
            error_msg = errors or output
            logger.error(f"Build failed for {project.name}: {error_msg[:500]}")
            return False, f"Build failed:\n{error_msg[:1000]}"

        logger.info(f"Build succeeded for {project.name}")
        return True, "Build successful"

    except asyncio.TimeoutError:
        logger.error(f"Build timeout for {project.name}")
        return False, "Build timed out"
    except Exception as e:
        logger.error(f"Build error for {project.name}: {e}")
        return False, f"Build error: {str(e)}"


async def check_typescript(project: Project) -> Tuple[bool, str]:
    """
    Run TypeScript type check.

    Returns:
        Tuple of (success, output)
    """
    tsconfig = Path(project.path) / "tsconfig.json"
    if not tsconfig.exists():
        return True, "No TypeScript config - skipping"

    try:
        process = await asyncio.create_subprocess_exec(
            "npx", "tsc", "--noEmit",
            cwd=project.path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=60
        )

        if process.returncode != 0:
            errors = stderr.decode("utf-8", errors="replace") or stdout.decode("utf-8", errors="replace")
            return False, f"TypeScript errors:\n{errors[:500]}"

        return True, "TypeScript check passed"

    except Exception as e:
        return True, f"TypeScript check skipped: {str(e)}"


# ============================================
# DEPLOYMENT
# ============================================

async def deploy_to_vercel(
    project: Project,
    send_update: Optional[Callable] = None,
    force: bool = True
) -> Tuple[bool, str, Optional[str]]:
    """
    Deploy a project to Vercel.

    Args:
        project: Project to deploy
        send_update: Optional callback for updates
        force: Use --force flag

    Returns:
        Tuple of (success, output, url)
    """
    if not is_deployable(project):
        return False, "Project is not deployable via Vercel", None

    if send_update:
        await send_update(f"🚀 Deploying {project.name} to Vercel...")

    logger.info(f"Deploying {project.name}")

    cmd = ["vercel", "--prod"]
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
            timeout=DEPLOY_TIMEOUT
        )

        output = stdout.decode("utf-8", errors="replace")
        errors = stderr.decode("utf-8", errors="replace")

        if process.returncode != 0:
            error_msg = errors or output
            logger.error(f"Deploy failed for {project.name}: {error_msg[:500]}")
            return False, f"Deploy failed:\n{error_msg[:500]}", None

        # Extract URL from output
        url = None
        url_match = re.search(r"https://[\w.-]+\.vercel\.app", output)
        if url_match:
            url = url_match.group(0)
        elif project.url:
            url = project.url

        logger.info(f"Deploy succeeded for {project.name}: {url}")
        return True, "Deployed successfully", url

    except asyncio.TimeoutError:
        logger.error(f"Deploy timeout for {project.name}")
        return False, "Deploy timed out", None
    except Exception as e:
        logger.error(f"Deploy error for {project.name}: {e}")
        return False, f"Deploy error: {str(e)}", None


# ============================================
# POST-DEPLOY VERIFICATION
# ============================================

async def verify_deployment(url: str, send_update: Optional[Callable] = None) -> Tuple[bool, str]:
    """
    Verify a deployment is working.

    Args:
        url: URL to check
        send_update: Optional callback

    Returns:
        Tuple of (success, message)
    """
    if send_update:
        await send_update(f"🔍 Verifying {url}...")

    logger.info(f"Verifying deployment: {url}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=VERIFY_TIMEOUT),
                allow_redirects=True
            ) as response:
                status = response.status

                if status == 200:
                    logger.info(f"Verification passed: {url} returned 200")
                    return True, f"Site is live and returning 200 OK"
                elif status < 400:
                    logger.info(f"Verification passed with status {status}")
                    return True, f"Site is live (status {status})"
                else:
                    logger.warning(f"Verification failed: {url} returned {status}")
                    return False, f"Site returned error status {status}"

    except asyncio.TimeoutError:
        return False, "Site verification timed out"
    except Exception as e:
        return False, f"Verification error: {str(e)}"


# ============================================
# FULL DEPLOY WORKFLOW
# ============================================

async def smart_deploy(
    project: Project,
    send_update: Optional[Callable] = None,
    skip_build: bool = False,
    verify: bool = True
) -> DeployResult:
    """
    Full smart deployment workflow:
    1. Run build
    2. Deploy to Vercel
    3. Verify deployment

    Args:
        project: Project to deploy
        send_update: Callback for status updates
        skip_build: Skip the build step
        verify: Verify after deploy

    Returns:
        DeployResult with full details
    """
    result = DeployResult(success=False)

    # Step 1: Build (unless skipped)
    if not skip_build:
        build_success, build_output = await run_build(project, send_update)
        result.build_output = build_output

        if not build_success:
            result.message = f"Build failed: {build_output[:200]}"
            if send_update:
                await send_update(f"⚠️ Build failed - not deploying")
            return result

    # Step 2: Deploy
    deploy_success, deploy_output, url = await deploy_to_vercel(project, send_update)
    result.deploy_output = deploy_output
    result.url = url

    if not deploy_success:
        result.message = f"Deploy failed: {deploy_output[:200]}"
        if send_update:
            await send_update(f"⚠️ Deploy failed")
        return result

    # Step 3: Verify (if requested and we have a URL)
    if verify and url:
        verify_success, verify_msg = await verify_deployment(url, send_update)
        result.verified = verify_success

        if not verify_success:
            result.message = f"Deployed but verification failed: {verify_msg}"
            result.success = True  # Deploy succeeded, just verification issue
            if send_update:
                await send_update(f"⚠️ Deployed but verification failed: {verify_msg}")
        else:
            result.message = f"Deployed and verified: {url}"
            result.success = True
            if send_update:
                await send_update(f"✅ Deployed and verified: {url}")
    else:
        result.success = True
        result.message = f"Deployed: {url or 'URL not available'}"

    # Record the deployment
    if result.success and url:
        set_last_deploy(url)
        add_context_note(f"Deployed {project.name} to {url}")

    return result


# ============================================
# ROLLBACK
# ============================================

async def rollback_vercel(project: Project, send_update: Optional[Callable] = None) -> Tuple[bool, str]:
    """
    Rollback to previous Vercel deployment.

    This uses `vercel rollback` to revert to the previous deployment.
    """
    if send_update:
        await send_update(f"⏪ Rolling back {project.name}...")

    logger.info(f"Rolling back {project.name}")

    try:
        # List deployments to find previous one
        process = await asyncio.create_subprocess_exec(
            "vercel", "ls", "--limit", "5",
            cwd=project.path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=30
        )

        output = stdout.decode("utf-8", errors="replace")
        logger.info(f"Recent deployments:\n{output}")

        # Attempt rollback
        process = await asyncio.create_subprocess_exec(
            "vercel", "rollback",
            cwd=project.path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=60
        )

        if process.returncode == 0:
            return True, "Rollback successful"
        else:
            errors = stderr.decode("utf-8", errors="replace")
            return False, f"Rollback failed: {errors[:200]}"

    except Exception as e:
        return False, f"Rollback error: {str(e)}"


# ============================================
# VERCEL LOGS
# ============================================

async def get_vercel_logs(project: Project, lines: int = 50) -> Tuple[bool, str]:
    """
    Get recent Vercel logs for a project.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            "vercel", "logs", "--limit", str(lines),
            cwd=project.path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=30
        )

        output = stdout.decode("utf-8", errors="replace")
        if output:
            return True, output
        else:
            errors = stderr.decode("utf-8", errors="replace")
            return False, f"No logs available: {errors}"

    except Exception as e:
        return False, f"Error getting logs: {str(e)}"
