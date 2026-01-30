"""
Kiyomi Skills System - Load and execute specialized skill files

Skills are markdown files with instructions for specific tasks.
Located in /Users/richardecholsai2/kiyomi/skills/
"""
import logging
from pathlib import Path
from typing import Optional, Dict, List
import re

logger = logging.getLogger(__name__)

# Skills directory
SKILLS_DIR = Path("/Users/richardecholsai2/kiyomi/skills")

# Cache loaded skills
_skills_cache: Dict[str, str] = {}
_skills_list: List[Dict] = []


def list_available_skills() -> List[Dict]:
    """List all available skill files."""
    global _skills_list

    if _skills_list:
        return _skills_list

    skills = []

    if not SKILLS_DIR.exists():
        logger.warning(f"Skills directory not found: {SKILLS_DIR}")
        return skills

    # Find all .md files in skills directory
    for skill_file in SKILLS_DIR.glob("*.md"):
        skill_name = skill_file.stem

        # Try to extract description from file
        description = ""
        try:
            content = skill_file.read_text()
            # Look for first heading or first paragraph
            lines = content.split("\n")
            for line in lines[1:10]:  # Check first 10 lines after title
                line = line.strip()
                if line and not line.startswith("#"):
                    description = line[:100]
                    break
        except:
            pass

        skills.append({
            "name": skill_name,
            "path": str(skill_file),
            "description": description
        })

    # Also check subdirectories
    for subdir in SKILLS_DIR.iterdir():
        if subdir.is_dir() and not subdir.name.startswith("."):
            for skill_file in subdir.glob("*.md"):
                skill_name = f"{subdir.name}/{skill_file.stem}"
                skills.append({
                    "name": skill_name,
                    "path": str(skill_file),
                    "description": ""
                })

    _skills_list = skills
    return skills


def load_skill(skill_name: str) -> Optional[str]:
    """
    Load a skill file by name.

    Args:
        skill_name: Name of the skill (without .md extension)

    Returns:
        Skill content or None if not found
    """
    global _skills_cache

    # Check cache
    if skill_name in _skills_cache:
        return _skills_cache[skill_name]

    # Try direct path
    skill_path = SKILLS_DIR / f"{skill_name}.md"
    if not skill_path.exists():
        # Try with SKILL suffix
        skill_path = SKILLS_DIR / f"{skill_name}_SKILL.md"
    if not skill_path.exists():
        # Try uppercase
        skill_path = SKILLS_DIR / f"{skill_name.upper()}_SKILL.md"
    if not skill_path.exists():
        # Search in subdirectories
        for subdir in SKILLS_DIR.iterdir():
            if subdir.is_dir():
                potential = subdir / f"{skill_name}.md"
                if potential.exists():
                    skill_path = potential
                    break

    if not skill_path.exists():
        logger.warning(f"Skill not found: {skill_name}")
        return None

    try:
        content = skill_path.read_text()
        _skills_cache[skill_name] = content
        logger.info(f"Loaded skill: {skill_name}")
        return content
    except Exception as e:
        logger.error(f"Error loading skill {skill_name}: {e}")
        return None


def get_skill_for_task(task_description: str) -> Optional[str]:
    """
    Automatically detect which skill might be relevant for a task.

    Args:
        task_description: Description of what needs to be done

    Returns:
        Skill name if one matches, None otherwise
    """
    task_lower = task_description.lower()

    # Mapping of keywords to skills
    skill_mappings = {
        # JW Content
        ("podcast", "jw", "meeting", "watchtower"): "jw-podcast-workflow",
        ("scripture", "nwt", "bible verse"): "scripture-nwt-lookup",
        ("kingdom watch", "news biblical"): "kingdom-watch-research",

        # Content Creation
        ("youtube", "upload", "video"): "youtube-upload-workflow",
        ("thumbnail",): "thumbnail-generation",
        ("transcript", "download video"): "video-transcript-downloader",
        ("slides", "presentation"): "frontend-slides",

        # Development
        ("frontend", "ui", "design", "css"): "frontend-design",
        ("react", "next.js", "vercel"): "vercel-react-best-practices",
        ("excel", "spreadsheet"): "excel",
        ("browser", "automate", "scrape"): "browser-use",

        # Productivity
        ("gmail", "google", "calendar", "drive"): "gog",
        ("github", "git", "repo"): "github",
        ("email", "imap"): "himalaya",
        ("apple notes", "notes app"): "apple-notes",
        ("reminders app", "apple reminders"): "apple-reminders",
        ("things", "things 3"): "things-mac",

        # Research
        ("twitter", "x.com", "tweet"): "search-x",
        ("news", "research"): "news-research-workflow",
        ("summarize", "summary"): "summarize",
        ("weather", "forecast"): "weather",
    }

    for keywords, skill_name in skill_mappings.items():
        if any(kw in task_lower for kw in keywords):
            return skill_name

    return None


def inject_skill_context(task: str) -> str:
    """
    Detect relevant skill and inject its content into the task context.

    Args:
        task: The original task description

    Returns:
        Task with skill context prepended if relevant
    """
    skill_name = get_skill_for_task(task)

    if not skill_name:
        return task

    skill_content = load_skill(skill_name)

    if not skill_content:
        return task

    # Truncate skill content if too long
    if len(skill_content) > 5000:
        skill_content = skill_content[:5000] + "\n\n...(truncated)"

    return f"""## Relevant Skill: {skill_name}

{skill_content}

---

## Task

{task}
"""


def clear_cache():
    """Clear the skills cache."""
    global _skills_cache, _skills_list
    _skills_cache = {}
    _skills_list = []


# Pre-load common skills on module import
def preload_common_skills():
    """Pre-load commonly used skills."""
    common_skills = [
        "MASTER_SKILL",
        "frontend-design",
        "NEXTJS_SUPABASE_SKILL",
    ]

    for skill in common_skills:
        load_skill(skill)


# Don't preload on import - do it lazily
