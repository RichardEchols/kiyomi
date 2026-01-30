"""
Kiyomi Milestones - Progress detection and updates

This module:
- Parses Claude CLI output for key milestones
- Sends updates at important points
- Provides structured progress tracking
"""
import re
import logging
from typing import Optional, List, Callable, Dict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class MilestoneType(Enum):
    """Types of milestones."""
    STARTED = "started"
    ANALYZING = "analyzing"
    FOUND_ISSUE = "found_issue"
    READING = "reading"
    WRITING = "writing"
    BUILDING = "building"
    TESTING = "testing"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    ERROR = "error"
    ROLLBACK = "rollback"


@dataclass
class Milestone:
    """A progress milestone."""
    type: MilestoneType
    message: str
    details: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    should_notify: bool = True


# ============================================
# MILESTONE DETECTION PATTERNS
# ============================================

MILESTONE_PATTERNS = [
    # Found issue patterns
    (r"found (?:the |an? )?(?:issue|problem|bug|error)", MilestoneType.FOUND_ISSUE, "Found the issue"),
    (r"(?:the |an? )?(?:issue|problem) (?:is|was|seems)", MilestoneType.FOUND_ISSUE, "Identified the problem"),
    (r"i see (?:the |an? )?(?:issue|problem|error)", MilestoneType.FOUND_ISSUE, "Found the issue"),

    # Reading patterns
    (r"reading [\w/.-]+", MilestoneType.READING, None),  # None = extract from match
    (r"read [\w/.-]+\.(?:ts|tsx|js|jsx|py|md)", MilestoneType.READING, None),
    (r"checking (?:the )?(?:code|file|config)", MilestoneType.READING, "Checking the code"),

    # Writing patterns
    (r"writing (?:to )?[\w/.-]+", MilestoneType.WRITING, None),
    (r"updating [\w/.-]+", MilestoneType.WRITING, None),
    (r"editing [\w/.-]+", MilestoneType.WRITING, None),
    (r"created? [\w/.-]+\.(?:ts|tsx|js|jsx|py)", MilestoneType.WRITING, None),
    (r"fix(?:ed|ing) (?:the )?(?:issue|problem|bug|error)", MilestoneType.WRITING, "Fixing the issue"),

    # Building patterns
    (r"npm run build", MilestoneType.BUILDING, "Building project"),
    (r"running build", MilestoneType.BUILDING, "Building project"),
    (r"compiling", MilestoneType.BUILDING, "Compiling"),
    (r"typescript.*compil", MilestoneType.BUILDING, "Compiling TypeScript"),

    # Testing patterns
    (r"running tests?", MilestoneType.TESTING, "Running tests"),
    (r"npm (?:run )?test", MilestoneType.TESTING, "Running tests"),
    (r"pytest", MilestoneType.TESTING, "Running tests"),

    # Deploying patterns
    (r"vercel --prod", MilestoneType.DEPLOYING, "Deploying to Vercel"),
    (r"deploying to", MilestoneType.DEPLOYING, "Deploying"),
    (r"pushing to (?:vercel|production)", MilestoneType.DEPLOYING, "Deploying"),

    # Deployed patterns
    (r"deployed? (?:successfully|to)", MilestoneType.DEPLOYED, "Deployed successfully"),
    (r"production.*ready", MilestoneType.DEPLOYED, "Deployed successfully"),
    (r"live at", MilestoneType.DEPLOYED, "Deployed successfully"),
    (r"https://[\w.-]+\.vercel\.app", MilestoneType.DEPLOYED, None),

    # Verification patterns
    (r"verif(?:y|ying|ied)", MilestoneType.VERIFYING, "Verifying deployment"),
    (r"checking (?:if |that )?(?:it |the site )(?:works|loads)", MilestoneType.VERIFYING, "Verifying site"),

    # Error patterns
    (r"error[:\s]", MilestoneType.ERROR, None),
    (r"failed", MilestoneType.ERROR, None),
    (r"couldn't|cannot|can't", MilestoneType.ERROR, None),

    # Completion patterns
    (r"done[!.]?$", MilestoneType.COMPLETED, "Done"),
    (r"completed?[!.]?$", MilestoneType.COMPLETED, "Completed"),
    (r"finished[!.]?$", MilestoneType.COMPLETED, "Finished"),
    (r"all set", MilestoneType.COMPLETED, "All set"),
]


# ============================================
# MILESTONE DETECTION
# ============================================

def detect_milestone(line: str) -> Optional[Milestone]:
    """
    Detect a milestone from a line of Claude output.

    Args:
        line: A line of text from Claude CLI output

    Returns:
        Milestone if detected, None otherwise
    """
    line_lower = line.lower().strip()

    if not line_lower or len(line_lower) < 3:
        return None

    for pattern, milestone_type, default_message in MILESTONE_PATTERNS:
        match = re.search(pattern, line_lower)
        if match:
            # Determine message
            if default_message:
                message = default_message
            else:
                # Extract from match
                message = match.group(0).capitalize()
                # Clean up message
                message = message.replace("  ", " ").strip()

            # Extract details (the full line, cleaned up)
            details = line.strip()[:200]

            # Determine if should notify (skip minor reads, notify important ones)
            should_notify = milestone_type in [
                MilestoneType.FOUND_ISSUE,
                MilestoneType.BUILDING,
                MilestoneType.DEPLOYING,
                MilestoneType.DEPLOYED,
                MilestoneType.ERROR,
                MilestoneType.COMPLETED,
            ]

            return Milestone(
                type=milestone_type,
                message=message,
                details=details,
                should_notify=should_notify
            )

    return None


def detect_milestones_in_text(text: str) -> List[Milestone]:
    """
    Detect all milestones in a block of text.

    Args:
        text: Claude CLI output text

    Returns:
        List of detected milestones
    """
    milestones = []
    seen_types = set()

    for line in text.split("\n"):
        milestone = detect_milestone(line)
        if milestone:
            # Avoid duplicate milestone types in quick succession
            if milestone.type not in seen_types or milestone.type == MilestoneType.ERROR:
                milestones.append(milestone)
                seen_types.add(milestone.type)

    return milestones


# ============================================
# MILESTONE FORMATTING
# ============================================

def format_milestone(milestone: Milestone) -> str:
    """
    Format a milestone for display to user.
    """
    emoji_map = {
        MilestoneType.STARTED: "🚀",
        MilestoneType.ANALYZING: "🔍",
        MilestoneType.FOUND_ISSUE: "🎯",
        MilestoneType.READING: "📖",
        MilestoneType.WRITING: "✏️",
        MilestoneType.BUILDING: "🔨",
        MilestoneType.TESTING: "🧪",
        MilestoneType.DEPLOYING: "🚀",
        MilestoneType.DEPLOYED: "✅",
        MilestoneType.VERIFYING: "🔍",
        MilestoneType.COMPLETED: "✅",
        MilestoneType.ERROR: "⚠️",
        MilestoneType.ROLLBACK: "⏪",
    }

    emoji = emoji_map.get(milestone.type, "📌")
    return f"{emoji} {milestone.message}"


# ============================================
# PROGRESS TRACKER
# ============================================

class ProgressTracker:
    """
    Track progress through a task and send updates.
    """

    def __init__(self, send_callback: Optional[Callable] = None):
        self.milestones: List[Milestone] = []
        self.send_callback = send_callback
        self.last_notification_time = datetime.now()
        self.min_notification_gap = 30  # Minimum seconds between notifications

    async def add_milestone(self, milestone: Milestone):
        """Add a milestone and potentially send notification."""
        self.milestones.append(milestone)

        if not milestone.should_notify or not self.send_callback:
            return

        # Check if enough time has passed since last notification
        elapsed = (datetime.now() - self.last_notification_time).total_seconds()
        if elapsed < self.min_notification_gap and milestone.type != MilestoneType.ERROR:
            return

        # Send notification
        message = format_milestone(milestone)
        try:
            await self.send_callback(message)
            self.last_notification_time = datetime.now()
            logger.info(f"Sent milestone notification: {milestone.type.value}")
        except Exception as e:
            logger.error(f"Failed to send milestone notification: {e}")

    def process_output_line(self, line: str) -> Optional[Milestone]:
        """Process a line of output and detect milestones."""
        milestone = detect_milestone(line)
        if milestone:
            # Don't await here - let caller handle async
            self.milestones.append(milestone)
        return milestone

    def get_summary(self) -> str:
        """Get a summary of all milestones."""
        if not self.milestones:
            return "No milestones recorded"

        summary_parts = []
        for m in self.milestones:
            summary_parts.append(f"- {format_milestone(m)}")

        return "\n".join(summary_parts)

    def has_errors(self) -> bool:
        """Check if any error milestones were recorded."""
        return any(m.type == MilestoneType.ERROR for m in self.milestones)

    def was_deployed(self) -> bool:
        """Check if deployment milestone was recorded."""
        return any(m.type == MilestoneType.DEPLOYED for m in self.milestones)


# ============================================
# SMART MESSAGE BUILDER
# ============================================

def build_progress_message(
    stage: str,
    project_name: Optional[str] = None,
    details: Optional[str] = None
) -> str:
    """
    Build a clean progress message.

    Args:
        stage: Current stage (analyzing, found_issue, fixing, deploying, done)
        project_name: Optional project name
        details: Optional details

    Returns:
        Formatted message
    """
    messages = {
        "analyzing": "Looking at the image...",
        "found_issue": "Found the issue",
        "checking": "Checking the code",
        "fixing": "Fixing it now",
        "building": "Building project",
        "deploying": "Deploying",
        "verifying": "Verifying deployment",
        "done": "Done!",
    }

    base = messages.get(stage, stage.capitalize())

    if project_name:
        base = f"{base} ({project_name})"

    if details:
        base = f"{base} - {details}"

    return base
