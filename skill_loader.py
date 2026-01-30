"""
Kiyomi Enhanced Skill Loader - Dynamic skill loading and management

Features:
- Load skills from markdown files
- Auto-detect relevant skills for tasks
- Skill composition (combine multiple skills)
- Skill versioning and updates
"""
import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any

import pytz
from config import TIMEZONE

logger = logging.getLogger(__name__)

# Skill directories
SKILLS_DIR = Path("/Users/richardecholsai2/kiyomi/skills")
EMPLOYEE_SKILLS_DIR = SKILLS_DIR / "employees"
PROJECT_SKILLS_DIR = SKILLS_DIR / "projects"


@dataclass
class Skill:
    """Represents a loaded skill."""
    name: str
    path: Path
    content: str
    description: str = ""
    triggers: List[str] = field(default_factory=list)  # Keywords that activate this skill
    category: str = "general"  # employee, project, tech, etc.
    priority: int = 0  # Higher = loaded first
    last_loaded: Optional[datetime] = None


# Skill cache
_skills_cache: Dict[str, Skill] = {}
_last_scan: Optional[datetime] = None
CACHE_TTL_MINUTES = 30


def scan_skills() -> Dict[str, Skill]:
    """Scan all skill directories and build skill index."""
    global _skills_cache, _last_scan

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    # Check cache freshness
    if _last_scan and (now - _last_scan).total_seconds() < CACHE_TTL_MINUTES * 60:
        return _skills_cache

    skills = {}

    # Scan main skills directory
    if SKILLS_DIR.exists():
        for skill_file in SKILLS_DIR.glob("*.md"):
            skill = _parse_skill_file(skill_file, "tech")
            if skill:
                skills[skill.name] = skill

    # Scan employee skills
    if EMPLOYEE_SKILLS_DIR.exists():
        for skill_file in EMPLOYEE_SKILLS_DIR.glob("*.md"):
            skill = _parse_skill_file(skill_file, "employee")
            if skill:
                skills[skill.name] = skill

    # Scan project skills
    if PROJECT_SKILLS_DIR.exists():
        for skill_file in PROJECT_SKILLS_DIR.glob("*.md"):
            skill = _parse_skill_file(skill_file, "project")
            if skill:
                skills[skill.name] = skill

    _skills_cache = skills
    _last_scan = now

    logger.info(f"Scanned {len(skills)} skills")
    return skills


def _parse_skill_file(path: Path, category: str) -> Optional[Skill]:
    """Parse a skill file and extract metadata."""
    try:
        content = path.read_text()

        # Extract name from filename
        name = path.stem.replace("_", " ").replace("-", " ").title()

        # Try to extract description from first paragraph
        description = ""
        lines = content.split("\n")
        for line in lines[:10]:
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("*"):
                description = line[:100]
                break

        # Extract triggers from content
        triggers = _extract_triggers(content, path.stem)

        # Determine priority
        priority = 0
        if "MASTER" in path.stem.upper():
            priority = 100
        elif "APPLE" in path.stem.upper() or "UI" in path.stem.upper():
            priority = 50

        return Skill(
            name=name,
            path=path,
            content=content,
            description=description,
            triggers=triggers,
            category=category,
            priority=priority
        )

    except Exception as e:
        logger.error(f"Error parsing skill {path}: {e}")
        return None


def _extract_triggers(content: str, filename: str) -> List[str]:
    """Extract trigger keywords from skill content."""
    triggers = []

    # Add filename-based triggers
    name_parts = filename.lower().replace("_", " ").replace("-", " ").split()
    triggers.extend(name_parts)

    # Common tech triggers
    tech_patterns = {
        "nextjs": ["next.js", "nextjs", "next js", "react", "vercel"],
        "supabase": ["supabase", "database", "postgres", "auth"],
        "streamlit": ["streamlit", "python", "data app"],
        "swift": ["swift", "ios", "iphone", "xcode", "apple"],
        "react": ["react", "jsx", "component"],
        "vite": ["vite", "react", "frontend"],
        "tailwind": ["tailwind", "css", "styling"],
        "apple": ["apple", "ui", "design", "polish"],
        "asana": ["asana", "task", "project management"],
    }

    content_lower = content.lower()
    for key, keywords in tech_patterns.items():
        if key in filename.lower() or any(kw in content_lower[:500] for kw in keywords):
            triggers.extend(keywords)

    # Employee triggers
    if "employee" in filename.lower() or "SKILLS_DIR/employees" in str(filename):
        employee_names = ["alex", "jordan", "sam", "casey", "morgan", "dev", "shield", "books", "pixel"]
        for name in employee_names:
            if name in filename.lower():
                triggers.append(name)

    return list(set(triggers))


def find_skills_for_task(task: str) -> List[Skill]:
    """Find relevant skills for a task based on triggers."""
    skills = scan_skills()
    task_lower = task.lower()

    matches = []
    for skill in skills.values():
        score = 0
        for trigger in skill.triggers:
            if trigger in task_lower:
                score += 1

        if score > 0:
            matches.append((skill, score))

    # Sort by score and priority
    matches.sort(key=lambda x: (x[1], x[0].priority), reverse=True)

    return [m[0] for m in matches[:5]]  # Top 5 matches


def load_skill(name: str) -> Optional[str]:
    """Load a skill by name and return its content."""
    skills = scan_skills()

    # Try exact match
    if name in skills:
        skill = skills[name]
        tz = pytz.timezone(TIMEZONE)
        skill.last_loaded = datetime.now(tz)
        return skill.content

    # Try partial match
    name_lower = name.lower()
    for skill_name, skill in skills.items():
        if name_lower in skill_name.lower():
            tz = pytz.timezone(TIMEZONE)
            skill.last_loaded = datetime.now(tz)
            return skill.content

    return None


def compose_skills(skill_names: List[str]) -> str:
    """Compose multiple skills into a single context."""
    contents = []

    for name in skill_names:
        content = load_skill(name)
        if content:
            contents.append(f"## Skill: {name}\n\n{content}")

    return "\n\n---\n\n".join(contents)


def get_skill_context_for_task(task: str) -> str:
    """Build skill context for a task."""
    relevant_skills = find_skills_for_task(task)

    if not relevant_skills:
        return ""

    # Always include master skill if it exists
    master_content = load_skill("Master Skill") or ""

    # Add relevant skills (limit to top 3 to avoid context bloat)
    skill_contents = []
    for skill in relevant_skills[:3]:
        if "master" not in skill.name.lower():
            skill_contents.append(f"## {skill.name}\n\n{skill.content[:2000]}")

    context = ""
    if master_content:
        context += f"## Master Skill\n\n{master_content[:1500]}\n\n---\n\n"

    if skill_contents:
        context += "\n\n---\n\n".join(skill_contents)

    return context


def list_skills() -> List[Dict]:
    """List all available skills."""
    skills = scan_skills()

    return [
        {
            "name": s.name,
            "category": s.category,
            "description": s.description[:80],
            "triggers": s.triggers[:5],
            "priority": s.priority
        }
        for s in sorted(skills.values(), key=lambda x: (-x.priority, x.name))
    ]


def get_skill_info(name: str) -> Optional[Dict]:
    """Get detailed info about a skill."""
    skills = scan_skills()

    for skill_name, skill in skills.items():
        if name.lower() in skill_name.lower():
            return {
                "name": skill.name,
                "path": str(skill.path),
                "category": skill.category,
                "description": skill.description,
                "triggers": skill.triggers,
                "priority": skill.priority,
                "content_preview": skill.content[:500] + "..." if len(skill.content) > 500 else skill.content,
                "last_loaded": skill.last_loaded.isoformat() if skill.last_loaded else None
            }

    return None


def format_skill_list() -> str:
    """Format skill list for display."""
    skills = list_skills()

    if not skills:
        return "No skills found."

    msg = "**Available Skills:**\n\n"

    # Group by category
    by_category = {}
    for s in skills:
        cat = s["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(s)

    for category, cat_skills in by_category.items():
        msg += f"**{category.title()}:**\n"
        for s in cat_skills[:10]:  # Limit per category
            msg += f"  • {s['name']}: {s['description'][:40]}...\n"
        msg += "\n"

    return msg
