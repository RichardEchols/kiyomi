"""
Kiyomi Project Registry - Know all of Richard's projects

This module provides:
- Project detection from text/images
- Project configs (path, tech, deploy, URL)
- Quick access to project info
"""
import re
import logging
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Project:
    """Project configuration."""
    name: str
    path: str
    tech: str
    deploy_cmd: str
    url: Optional[str] = None
    description: str = ""
    aliases: List[str] = None

    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []


# ============================================
# PROJECT REGISTRY
# ============================================

PROJECTS: Dict[str, Project] = {
    "true-podcasts": Project(
        name="True Podcasts",
        path="/Users/richardecholsai2/Documents/Apps/true-podcasts",
        tech="Next.js + Tailwind + Supabase",
        deploy_cmd="vercel --prod --force",
        url="https://true-podcasts.vercel.app",
        description="JW podcast generation app",
        aliases=["true podcasts", "truepodcasts", "podcast app", "jw podcasts"]
    ),

    "jw-companion": Project(
        name="JW Companion",
        path="/Users/richardecholsai2/Documents/Apps/jw-companion",
        tech="React + Vite + Tailwind",
        deploy_cmd="vercel --prod --force",
        url="https://jw-companion.vercel.app",
        description="JW study companion app",
        aliases=["jw companion", "jwcompanion", "companion app"]
    ),

    "nano-banana-studio": Project(
        name="Nano Banana Studio",
        path="/Users/richardecholsai2/Documents/Apps/nano-banana-studio",
        tech="Python + Streamlit",
        deploy_cmd="# Streamlit Cloud deploy",
        url="https://nano-banana-studio.streamlit.app",
        description="AI image generation studio",
        aliases=["nano banana", "nanobanana", "banana studio", "image studio"]
    ),

    "yt-automation": Project(
        name="YT Automation",
        path="/Users/richardecholsai2/Documents/Apps/YTAutomation",
        tech="Python",
        deploy_cmd="# Local script",
        url=None,
        description="YouTube automation scripts",
        aliases=["youtube automation", "yt automation", "youtube scripts"]
    ),

    "premier-intelligence": Project(
        name="Premier Intelligence",
        path="/Users/richardecholsai2/Desktop/Work/premier-intelligence-assistant",
        tech="Next.js + Supabase",
        deploy_cmd="vercel --prod --force",
        url="https://premier-intelligence.vercel.app",
        description="Client project - Premier Intelligence",
        aliases=["premier intelligence", "premier", "intelligence assistant"]
    ),

    "healthquest": Project(
        name="HealthQuest",
        path="/Users/richardecholsai2/Documents/Apps/HealthQuest",
        tech="Swift iOS",
        deploy_cmd="# Xcode build",
        url=None,
        description="iOS health tracking app",
        aliases=["health quest", "healthquest", "health app", "ios app"]
    ),

    "keiko-telegram-bot": Project(
        name="Kiyomi Bot",
        path="/Users/richardecholsai2/Documents/Apps/keiko-telegram-bot",
        tech="Python + Telegram",
        deploy_cmd="launchctl kickstart -k gui/$(id -u)/com.richardechols.keiko",
        url=None,
        description="This bot!",
        aliases=["keiko", "kiyomi bot", "telegram bot", "this bot"]
    ),

    "richard-portfolio": Project(
        name="Richard's Portfolio",
        path="/Users/richardecholsai2/Documents/Apps/richardechols-portfolio",
        tech="Next.js + Tailwind",
        deploy_cmd="vercel --prod --force",
        url="https://richardechols.com",
        description="Personal portfolio site",
        aliases=["portfolio", "my site", "richardechols.com", "personal site"]
    ),
}


# ============================================
# PROJECT DETECTION
# ============================================

def detect_project_from_text(text: str) -> Optional[Project]:
    """
    Detect which project is being discussed from text.

    Args:
        text: Message text or image caption

    Returns:
        Project if detected, None otherwise
    """
    text_lower = text.lower()

    # Check each project and its aliases
    for project_id, project in PROJECTS.items():
        # Check project name
        if project.name.lower() in text_lower:
            logger.info(f"Detected project from name: {project.name}")
            return project

        # Check project ID
        if project_id in text_lower:
            logger.info(f"Detected project from ID: {project_id}")
            return project

        # Check aliases
        for alias in project.aliases:
            if alias in text_lower:
                logger.info(f"Detected project from alias '{alias}': {project.name}")
                return project

    # Check for URL mentions
    for project_id, project in PROJECTS.items():
        if project.url and project.url in text:
            logger.info(f"Detected project from URL: {project.name}")
            return project

    # Check for path mentions
    for project_id, project in PROJECTS.items():
        if project.path in text:
            logger.info(f"Detected project from path: {project.name}")
            return project

    return None


def detect_project_from_image_text(ocr_text: str) -> Optional[Project]:
    """
    Detect project from text extracted from an image.
    Looks for UI elements, URLs, app names.
    """
    # Use same logic as text detection
    project = detect_project_from_text(ocr_text)
    if project:
        return project

    # Additional image-specific patterns
    patterns = {
        "true-podcasts": [r"true\s*podcasts?", r"podcast.*generation", r"meeting.*workbook"],
        "jw-companion": [r"jw\s*companion", r"bible.*study"],
        "nano-banana": [r"nano.*banana", r"image.*generat"],
    }

    ocr_lower = ocr_text.lower()
    for project_id, pats in patterns.items():
        for pat in pats:
            if re.search(pat, ocr_lower):
                return PROJECTS.get(project_id)

    return None


def get_project(project_id: str) -> Optional[Project]:
    """Get a project by ID."""
    return PROJECTS.get(project_id)


def get_project_by_name(name: str) -> Optional[Project]:
    """Get a project by name (fuzzy match)."""
    name_lower = name.lower()

    for project_id, project in PROJECTS.items():
        if project.name.lower() == name_lower or project_id == name_lower:
            return project
        for alias in project.aliases:
            if alias == name_lower:
                return project

    return None


def list_projects() -> List[Project]:
    """List all registered projects."""
    return list(PROJECTS.values())


def get_project_context(project: Project) -> str:
    """
    Get context string for a project to inject into prompts.
    """
    context = f"""## Active Project: {project.name}

**Path:** {project.path}
**Tech:** {project.tech}
**Deploy:** `{project.deploy_cmd}`
"""
    if project.url:
        context += f"**URL:** {project.url}\n"

    context += f"**Description:** {project.description}\n"

    return context


# ============================================
# QUICK COMMANDS
# ============================================

def parse_quick_command(text: str) -> Optional[Dict]:
    """
    Parse quick commands like 'deploy true-podcasts' or 'logs jw-companion'.

    Returns:
        Dict with 'command' and 'project' keys, or None
    """
    text_lower = text.lower().strip()

    # Deploy command
    deploy_match = re.match(r"deploy\s+(.+)", text_lower)
    if deploy_match:
        project_name = deploy_match.group(1).strip()
        project = get_project_by_name(project_name)
        if project:
            return {"command": "deploy", "project": project}

    # Logs command
    logs_match = re.match(r"logs?\s+(.+)", text_lower)
    if logs_match:
        project_name = logs_match.group(1).strip()
        project = get_project_by_name(project_name)
        if project:
            return {"command": "logs", "project": project}

    # Status command
    status_match = re.match(r"status\s+(.+)", text_lower)
    if status_match:
        project_name = status_match.group(1).strip()
        project = get_project_by_name(project_name)
        if project:
            return {"command": "status", "project": project}

    # Rollback command
    rollback_match = re.match(r"rollback\s+(.+)", text_lower)
    if rollback_match:
        project_name = rollback_match.group(1).strip()
        project = get_project_by_name(project_name)
        if project:
            return {"command": "rollback", "project": project}

    return None


# ============================================
# PROJECT PATH UTILITIES
# ============================================

def get_project_from_path(file_path: str) -> Optional[Project]:
    """Detect project from a file path."""
    for project_id, project in PROJECTS.items():
        if file_path.startswith(project.path):
            return project
    return None


def is_deployable(project: Project) -> bool:
    """Check if a project can be deployed via Vercel."""
    return "vercel" in project.deploy_cmd.lower()


def get_vercel_projects() -> List[Project]:
    """Get all projects that deploy to Vercel."""
    return [p for p in PROJECTS.values() if is_deployable(p)]
