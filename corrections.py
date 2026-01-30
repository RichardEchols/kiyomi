"""
Kiyomi Corrections Learning - Learn from user corrections

Features:
- Detect when Richard corrects Kiyomi
- Extract the preference/correction
- Store and apply in future interactions
- Build preference profile over time
"""
import asyncio
import logging
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple

import pytz
from config import BASE_DIR, TIMEZONE, WORKSPACE_DIR

logger = logging.getLogger(__name__)

# Corrections configuration
CORRECTIONS_FILE = BASE_DIR / "corrections.json"
PREFERENCES_FILE = WORKSPACE_DIR / "PREFERENCES.md"
MAX_CORRECTIONS = 200


@dataclass
class Correction:
    """Represents a correction from Richard."""
    timestamp: datetime
    original_response: str
    correction_text: str
    extracted_preference: str
    category: str  # style, behavior, technical, communication
    applied: bool = False


# Correction patterns that indicate Richard is correcting something
CORRECTION_PATTERNS = [
    r"^no,?\s+",                        # "No, ..."
    r"^not\s+like\s+that",              # "Not like that"
    r"^that'?s\s+(?:not\s+)?wrong",     # "That's wrong"
    r"^actually,?\s+",                  # "Actually, ..."
    r"^instead,?\s+",                   # "Instead, ..."
    r"^I\s+(?:meant|want|need)",        # "I meant/want/need"
    r"^don'?t\s+",                      # "Don't ..."
    r"^please\s+(?:don'?t|stop)",       # "Please don't/stop"
    r"^wrong",                          # "Wrong"
    r"^that'?s\s+not\s+what",           # "That's not what..."
    r"^I\s+said",                       # "I said..."
    r"^never\s+",                       # "Never..."
    r"^always\s+",                      # "Always..."
    r"^remember\s+(?:to|that)",         # "Remember to/that..."
    r"^from\s+now\s+on",                # "From now on..."
    r"^in\s+the\s+future",              # "In the future..."
    r"^next\s+time",                    # "Next time..."
]

# Preference categories
PREFERENCE_CATEGORIES = {
    "style": ["format", "style", "look", "design", "ui", "appearance", "color", "font"],
    "behavior": ["always", "never", "automatically", "by default", "should", "shouldn't"],
    "technical": ["deploy", "build", "code", "api", "database", "server", "git"],
    "communication": ["tell me", "don't tell", "notify", "update", "silent", "verbose", "brief"]
}


def detect_correction(message: str, last_kiyomi_response: Optional[str] = None) -> bool:
    """
    Detect if a message is a correction.
    """
    message_lower = message.lower().strip()

    # Check explicit patterns
    for pattern in CORRECTION_PATTERNS:
        if re.match(pattern, message_lower, re.IGNORECASE):
            return True

    # Check for preference indicators
    preference_words = ["prefer", "rather", "instead", "better", "should", "shouldn't", "don't like"]
    if any(word in message_lower for word in preference_words):
        return True

    return False


def categorize_preference(text: str) -> str:
    """Categorize a preference based on keywords."""
    text_lower = text.lower()

    for category, keywords in PREFERENCE_CATEGORIES.items():
        if any(kw in text_lower for kw in keywords):
            return category

    return "general"


async def extract_preference(
    correction_text: str,
    original_response: Optional[str] = None
) -> Tuple[str, str]:
    """
    Use Claude to extract the preference from a correction.
    Returns (preference, category).
    """
    prompt = f"""Richard corrected Kiyomi with this message:

CORRECTION: {correction_text}

{f'KEIKO SAID BEFORE: {original_response[:200]}...' if original_response else ''}

Extract the underlying preference or rule Richard wants Kiyomi to follow.
Express it as a clear, actionable instruction.

Examples:
- "No, use dark mode not light" → "Always use dark mode for UI designs"
- "Don't ask, just do it" → "Be autonomous - execute tasks without asking permission"
- "That's too long, keep it brief" → "Keep responses concise and brief"

Return ONLY the extracted preference, nothing else. Keep it under 100 characters."""

    try:
        process = await asyncio.create_subprocess_exec(
            "/Users/richardecholsai2/.local/bin/claude",
            "-p", prompt,
            "--dangerously-skip-permissions",
            cwd="/Users/richardecholsai2/Apps",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30)
        preference = stdout.decode("utf-8", errors="replace").strip()

        # Clean up the preference
        preference = preference.strip('"\'').strip()
        if len(preference) > 150:
            preference = preference[:150]

        category = categorize_preference(preference)

        return preference, category

    except Exception as e:
        logger.error(f"Error extracting preference: {e}")
        # Fallback: use the correction text directly
        return correction_text[:100], categorize_preference(correction_text)


def _load_corrections() -> List[Dict]:
    """Load corrections from file."""
    try:
        if CORRECTIONS_FILE.exists():
            with open(CORRECTIONS_FILE) as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading corrections: {e}")
    return []


def _save_corrections(corrections: List[Dict]) -> None:
    """Save corrections to file."""
    try:
        # Keep only recent corrections
        corrections = corrections[-MAX_CORRECTIONS:]
        with open(CORRECTIONS_FILE, "w") as f:
            json.dump(corrections, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving corrections: {e}")


async def learn_from_correction(
    correction_text: str,
    original_response: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Learn from a correction and store the preference.
    Returns (success, extracted_preference).
    """
    tz = pytz.timezone(TIMEZONE)

    # Extract the preference
    preference, category = await extract_preference(correction_text, original_response)

    if not preference:
        return False, "Could not extract preference"

    # Create correction record
    correction = {
        "timestamp": datetime.now(tz).isoformat(),
        "original_response": original_response[:200] if original_response else None,
        "correction_text": correction_text[:500],
        "extracted_preference": preference,
        "category": category,
        "applied": True
    }

    # Load existing corrections
    corrections = _load_corrections()

    # Check for duplicates
    existing_prefs = [c.get("extracted_preference", "").lower() for c in corrections]
    if preference.lower() not in existing_prefs:
        corrections.append(correction)
        _save_corrections(corrections)

        # Update PREFERENCES.md
        _update_preferences_file(preference, category)

        logger.info(f"Learned preference: {preference}")
        return True, preference
    else:
        logger.info(f"Preference already known: {preference}")
        return True, f"(already knew) {preference}"


def _update_preferences_file(preference: str, category: str) -> None:
    """Update the PREFERENCES.md file with new preference."""
    try:
        tz = pytz.timezone(TIMEZONE)
        timestamp = datetime.now(tz).strftime("%Y-%m-%d")

        # Load or create preferences file
        if PREFERENCES_FILE.exists():
            content = PREFERENCES_FILE.read_text()
        else:
            content = """# Richard's Preferences

*Learned from corrections and explicit instructions.*

---

## Style Preferences

## Behavior Preferences

## Technical Preferences

## Communication Preferences

## General Preferences

---

*Updated automatically when Richard corrects Kiyomi.*
"""

        # Find the right section
        section_map = {
            "style": "## Style Preferences",
            "behavior": "## Behavior Preferences",
            "technical": "## Technical Preferences",
            "communication": "## Communication Preferences",
            "general": "## General Preferences"
        }

        section_header = section_map.get(category, "## General Preferences")

        # Add preference under section
        new_entry = f"\n- {preference} _{timestamp}_"

        if section_header in content:
            # Find the section and add after it
            parts = content.split(section_header)
            if len(parts) == 2:
                # Find next section or end
                after_header = parts[1]
                next_section = after_header.find("\n## ")
                if next_section == -1:
                    next_section = after_header.find("\n---")

                if next_section != -1:
                    # Insert before next section
                    new_after = after_header[:next_section] + new_entry + after_header[next_section:]
                else:
                    # Append to end of section
                    new_after = after_header + new_entry

                content = parts[0] + section_header + new_after

        PREFERENCES_FILE.write_text(content)

    except Exception as e:
        logger.error(f"Error updating preferences file: {e}")


def get_preferences_for_context() -> str:
    """
    Get preferences formatted for inclusion in context.
    Returns a concise list of key preferences.
    """
    corrections = _load_corrections()

    if not corrections:
        return ""

    # Get unique preferences by category
    by_category = {}
    for c in corrections[-30:]:  # Last 30 corrections
        cat = c.get("category", "general")
        pref = c.get("extracted_preference", "")
        if cat not in by_category:
            by_category[cat] = []
        if pref and pref not in by_category[cat]:
            by_category[cat].append(pref)

    # Build context string
    context = "## Richard's Preferences (Learned)\n"
    for cat, prefs in by_category.items():
        if prefs:
            context += f"\n**{cat.title()}:**\n"
            for pref in prefs[-5:]:  # Last 5 per category
                context += f"- {pref}\n"

    return context


def get_all_preferences() -> Dict[str, List[str]]:
    """Get all preferences grouped by category."""
    corrections = _load_corrections()

    by_category = {}
    for c in corrections:
        cat = c.get("category", "general")
        pref = c.get("extracted_preference", "")
        if cat not in by_category:
            by_category[cat] = []
        if pref and pref not in by_category[cat]:
            by_category[cat].append(pref)

    return by_category


def get_correction_stats() -> Dict:
    """Get statistics about corrections."""
    corrections = _load_corrections()

    total = len(corrections)
    if total == 0:
        return {"total": 0}

    by_category = {}
    for c in corrections:
        cat = c.get("category", "general")
        by_category[cat] = by_category.get(cat, 0) + 1

    # Recent corrections (last 7 days)
    tz = pytz.timezone(TIMEZONE)
    week_ago = datetime.now(tz).timestamp() - (7 * 24 * 60 * 60)
    recent = sum(1 for c in corrections
                 if datetime.fromisoformat(c["timestamp"]).timestamp() > week_ago)

    return {
        "total": total,
        "by_category": by_category,
        "recent_week": recent,
        "unique_preferences": len(set(c.get("extracted_preference", "") for c in corrections))
    }


async def process_potential_correction(
    message: str,
    last_kiyomi_response: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Process a message that might be a correction.
    Returns (was_correction, learned_preference).
    """
    if not detect_correction(message, last_kiyomi_response):
        return False, None

    success, preference = await learn_from_correction(message, last_kiyomi_response)
    return True, preference if success else None
