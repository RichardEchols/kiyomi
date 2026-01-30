"""
Kiyomi Smart Response - Intelligent clarification, confidence, and error recovery

Features:
- Smart clarification (ask ONE good question when uncertain)
- Confidence signaling
- Inline refinement detection
- Auto error recovery
"""
import asyncio
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Tuple, Dict, Any

from config import BASE_DIR

logger = logging.getLogger(__name__)


class ConfidenceLevel(Enum):
    HIGH = "high"           # "I see the issue, fixing now"
    MEDIUM = "medium"       # "I think I understand, let me try"
    LOW = "low"             # "I'm not sure, let me clarify"
    UNCERTAIN = "uncertain" # "I need more info"


class TaskType(Enum):
    FIX_ERROR = "fix_error"
    DEPLOY = "deploy"
    CREATE = "create"
    MODIFY = "modify"
    RESEARCH = "research"
    EXPLAIN = "explain"
    OTHER = "other"


@dataclass
class TaskAnalysis:
    """Analysis of a user request."""
    task_type: TaskType
    confidence: ConfidenceLevel
    detected_project: Optional[str]
    detected_files: List[str]
    is_refinement: bool
    refinement_of: Optional[str]
    needs_clarification: bool
    clarification_question: Optional[str]
    suggested_approach: Optional[str]


# Patterns that indicate low confidence / need clarification
AMBIGUOUS_PATTERNS = [
    (r"^(?:do|make|change|update|fix)\s+(?:it|this|that)$", "What specifically should I work on?"),
    (r"^(?:the\s+)?(?:same|usual|normal)\s+(?:thing|way)$", "Could you remind me what the usual approach is?"),
    (r"^(?:you\s+)?know\s+what\s+(?:i\s+)?mean", "I want to make sure I understand - could you be more specific?"),
    (r"something\s+(?:like|similar)", "Could you give me a specific example of what you're looking for?"),
]

# Patterns that indicate refinement of previous task
REFINEMENT_PATTERNS = [
    r"^no[,.]?\s+",
    r"^not\s+(?:like\s+)?that",
    r"^actually[,.]?\s+",
    r"^instead[,.]?\s+",
    r"^but\s+",
    r"^try\s+(?:it\s+)?(?:this|another)\s+way",
    r"^(?:I\s+)?meant\s+",
    r"^that'?s\s+not\s+(?:what|right)",
    r"^wrong",
    r"^different",
]

# Patterns for task type detection
TASK_PATTERNS = {
    TaskType.FIX_ERROR: [
        r"fix\s+(?:the\s+)?(?:error|bug|issue|problem)",
        r"(?:error|bug|issue)\s+(?:in|with|on)",
        r"not\s+working",
        r"broken",
        r"crash",
    ],
    TaskType.DEPLOY: [
        r"deploy",
        r"push\s+(?:to\s+)?(?:prod|production|live)",
        r"ship\s+it",
        r"go\s+live",
    ],
    TaskType.CREATE: [
        r"create\s+(?:a\s+)?(?:new)?",
        r"add\s+(?:a\s+)?(?:new)?",
        r"build\s+(?:a\s+)?(?:new)?",
        r"make\s+(?:a\s+)?(?:new)?",
        r"set\s*up",
    ],
    TaskType.MODIFY: [
        r"change\s+",
        r"update\s+",
        r"modify\s+",
        r"edit\s+",
        r"refactor",
    ],
    TaskType.RESEARCH: [
        r"(?:what|how|why|where|when)\s+",
        r"find\s+(?:out|where|how)",
        r"look\s+(?:up|into|for)",
        r"search\s+",
        r"check\s+(?:if|whether)",
    ],
    TaskType.EXPLAIN: [
        r"explain\s+",
        r"tell\s+me\s+(?:about|how|why)",
        r"what\s+(?:is|are|does)",
        r"how\s+does",
    ],
}


def analyze_task(
    message: str,
    last_kiyomi_response: Optional[str] = None,
    last_user_message: Optional[str] = None,
    current_project: Optional[str] = None
) -> TaskAnalysis:
    """
    Analyze a user message to understand intent and confidence level.
    """
    message_lower = message.lower().strip()

    # Check if this is a refinement
    is_refinement = False
    refinement_of = None
    for pattern in REFINEMENT_PATTERNS:
        if re.match(pattern, message_lower):
            is_refinement = True
            refinement_of = last_user_message
            break

    # Detect task type
    task_type = TaskType.OTHER
    for ttype, patterns in TASK_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, message_lower):
                task_type = ttype
                break
        if task_type != TaskType.OTHER:
            break

    # Check for ambiguity
    needs_clarification = False
    clarification_question = None
    for pattern, question in AMBIGUOUS_PATTERNS:
        if re.match(pattern, message_lower):
            needs_clarification = True
            clarification_question = question
            break

    # Detect project mentions
    detected_project = current_project
    from projects import list_projects
    for project in list_projects():
        if project.name.lower() in message_lower or \
           project.name.lower().replace(" ", "-") in message_lower:
            detected_project = project.name
            break

    # Detect file mentions
    detected_files = []
    file_patterns = [
        r'[\w-]+\.(?:py|js|ts|tsx|jsx|md|json|css|html)',
        r'(?:src|components|pages|lib|utils)/[\w/-]+',
    ]
    for pattern in file_patterns:
        matches = re.findall(pattern, message)
        detected_files.extend(matches)

    # Determine confidence level
    if needs_clarification:
        confidence = ConfidenceLevel.UNCERTAIN
    elif is_refinement:
        confidence = ConfidenceLevel.HIGH  # Refinements are usually clear
    elif detected_project or detected_files or task_type != TaskType.OTHER:
        confidence = ConfidenceLevel.HIGH
    elif len(message.split()) < 5 and not any([detected_project, detected_files]):
        confidence = ConfidenceLevel.LOW
    else:
        confidence = ConfidenceLevel.MEDIUM

    # Generate suggested approach
    suggested_approach = _generate_approach(task_type, detected_project, message)

    return TaskAnalysis(
        task_type=task_type,
        confidence=confidence,
        detected_project=detected_project,
        detected_files=detected_files,
        is_refinement=is_refinement,
        refinement_of=refinement_of,
        needs_clarification=needs_clarification,
        clarification_question=clarification_question,
        suggested_approach=suggested_approach
    )


def _generate_approach(task_type: TaskType, project: Optional[str], message: str) -> str:
    """Generate a suggested approach based on task type."""
    approaches = {
        TaskType.FIX_ERROR: "I'll read the error, find the issue, fix it, and verify",
        TaskType.DEPLOY: f"I'll build {project or 'the project'}, deploy to Vercel, and verify it's live",
        TaskType.CREATE: "I'll create the new component/feature and integrate it",
        TaskType.MODIFY: "I'll find the relevant code, make the changes, and test",
        TaskType.RESEARCH: "I'll search the codebase and explain what I find",
        TaskType.EXPLAIN: "I'll analyze and provide a clear explanation",
        TaskType.OTHER: "I'll analyze this and take appropriate action"
    }
    return approaches.get(task_type, approaches[TaskType.OTHER])


def get_confidence_prefix(analysis: TaskAnalysis) -> str:
    """Get the appropriate response prefix based on confidence."""
    if analysis.is_refinement:
        return "Got it, adjusting approach."

    prefixes = {
        ConfidenceLevel.HIGH: f"On it. {analysis.suggested_approach}.",
        ConfidenceLevel.MEDIUM: f"I think I understand. {analysis.suggested_approach}.",
        ConfidenceLevel.LOW: "Let me make sure I understand...",
        ConfidenceLevel.UNCERTAIN: ""  # Will ask clarification instead
    }
    return prefixes.get(analysis.confidence, "On it.")


def should_ask_clarification(analysis: TaskAnalysis) -> Tuple[bool, Optional[str]]:
    """
    Determine if we should ask for clarification.
    Returns (should_ask, question).

    Only asks if genuinely uncertain AND the question would be helpful.
    """
    if not analysis.needs_clarification:
        return False, None

    # Don't ask if we have enough context
    if analysis.detected_project and analysis.task_type != TaskType.OTHER:
        return False, None

    return True, analysis.clarification_question


# ============================================
# ERROR RECOVERY
# ============================================

@dataclass
class RecoveryStrategy:
    """A strategy for recovering from an error."""
    description: str
    prompt_modification: str
    should_retry: bool = True


ERROR_RECOVERY_STRATEGIES = {
    "module_not_found": RecoveryStrategy(
        description="Install missing module",
        prompt_modification="First run 'npm install' or 'pip install' for missing dependencies, then retry the original task."
    ),
    "build_failed": RecoveryStrategy(
        description="Fix build errors",
        prompt_modification="Read the build error carefully, fix the syntax/import issue, then build again."
    ),
    "deploy_failed": RecoveryStrategy(
        description="Retry deployment",
        prompt_modification="Check Vercel logs for the issue, fix if needed, then deploy with --force flag."
    ),
    "file_not_found": RecoveryStrategy(
        description="Find correct file",
        prompt_modification="Search for the file in the codebase using glob, then proceed with the correct path."
    ),
    "permission_denied": RecoveryStrategy(
        description="Fix permissions",
        prompt_modification="Check file permissions, fix if needed (chmod), then retry."
    ),
    "timeout": RecoveryStrategy(
        description="Retry with simpler approach",
        prompt_modification="The previous attempt timed out. Try a simpler approach or break into smaller steps."
    ),
}


def detect_error_type(error_text: str) -> Optional[str]:
    """Detect the type of error from error text."""
    error_lower = error_text.lower()

    patterns = {
        "module_not_found": ["module not found", "cannot find module", "no module named", "modulenotfounderror"],
        "build_failed": ["build failed", "compilation error", "syntax error", "type error"],
        "deploy_failed": ["deploy failed", "deployment error", "vercel error"],
        "file_not_found": ["file not found", "no such file", "enoent", "filenotfounderror"],
        "permission_denied": ["permission denied", "eacces", "access denied"],
        "timeout": ["timeout", "timed out", "took too long"],
    }

    for error_type, keywords in patterns.items():
        if any(kw in error_lower for kw in keywords):
            return error_type

    return None


def get_recovery_strategy(error_text: str) -> Optional[RecoveryStrategy]:
    """Get a recovery strategy for an error."""
    error_type = detect_error_type(error_text)
    if error_type:
        return ERROR_RECOVERY_STRATEGIES.get(error_type)
    return None


async def attempt_recovery(
    original_prompt: str,
    error_text: str,
    execute_fn,  # The execute_claude function
    max_retries: int = 2
) -> Tuple[bool, str]:
    """
    Attempt to recover from an error automatically.

    Returns (success, result).
    """
    strategy = get_recovery_strategy(error_text)

    if not strategy or not strategy.should_retry:
        return False, error_text

    for attempt in range(max_retries):
        logger.info(f"Recovery attempt {attempt + 1}: {strategy.description}")

        # Build recovery prompt
        recovery_prompt = f"""Previous attempt failed with error:
{error_text[:500]}

Recovery strategy: {strategy.description}

{strategy.prompt_modification}

Original task: {original_prompt}

Try again with the recovery approach."""

        result, success = await execute_fn(recovery_prompt, check_for_swarm=False)

        if success:
            return True, result

        # Check if same error - if so, give up
        if detect_error_type(result) == detect_error_type(error_text):
            break

    return False, f"Recovery failed after {max_retries} attempts. Last error: {result}"
