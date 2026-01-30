"""
Kiyomi Executor - Claude Code CLI wrapper with persistent memory

Enhanced with:
- Project awareness
- Milestone tracking
- Session state
- Smart deployment
"""
import asyncio
import subprocess
import logging
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Callable
from config import BASE_DIR, WORKSPACE_DIR, MEMORY_DIR, TIMEZONE
from pathlib import Path as PathLib
from skills import inject_skill_context, get_skill_for_task
from projects import detect_project_from_text, get_project_context, Project
from session_state import (
    get_state, set_current_project, get_current_project_name,
    set_last_error, add_context_note, build_session_context,
    resolve_reference, is_continuation
)
from milestones import ProgressTracker, detect_milestone, format_milestone
from corrections import detect_correction, process_potential_correction, get_preferences_for_context
from cost_tracking import log_api_call, estimate_tokens, check_alerts, get_daily_cost
from escalation import handle_error, classify_error, Severity
from session_manager import (
    get_current_session, start_session, update_session, end_session,
    get_continuation_context, should_continue, is_continue_command,
    get_continue_prompt, mark_needs_continuation
)
from smart_response import (
    analyze_task, get_confidence_prefix, should_ask_clarification,
    get_recovery_strategy, attempt_recovery, TaskAnalysis
)

# Additional context files to always inject
try:
    from config import SKILLS_DIR as _SKILLS_DIR_STR, MASTER_ENV_FILE as _MASTER_ENV_STR, APPS_DIR, CLAUDE_CLI_PATH
except ImportError:
    _SKILLS_DIR_STR = None
    _MASTER_ENV_STR = None
    APPS_DIR = '/Users/richardecholsai2/projects'
    CLAUDE_CLI_PATH = '/opt/homebrew/bin/claude'
SKILLS_DIR = PathLib(_SKILLS_DIR_STR) if _SKILLS_DIR_STR else None
STARTUP_FILE = WORKSPACE_DIR / "STARTUP.md"
SESSION_LOG_FILE = WORKSPACE_DIR / "SESSION_LOG.md"
ACTIVE_PROJECT_FILE = WORKSPACE_DIR / "ACTIVE_PROJECT.md"
MASTER_SKILL_FILE = PathLib(_SKILLS_DIR_STR) / "MASTER_SKILL.md" if _SKILLS_DIR_STR else None
MASTER_ENV_FILE = PathLib(_MASTER_ENV_STR) if _MASTER_ENV_STR else None
import pytz

logger = logging.getLogger(__name__)

# Max response length before truncation
MAX_RESPONSE_LENGTH = 50000
TIMEOUT_SECONDS = 1800  # 30 minutes for complex tasks

# Track current running process for cancellation
_current_process: Optional[asyncio.subprocess.Process] = None
_current_task_description: Optional[str] = None

# Sub-agent tracking
_running_subagents: Dict[str, asyncio.subprocess.Process] = {}
SUBAGENT_LOG_DIR = BASE_DIR / "subagent_logs"

# Conversation history settings
CONVERSATION_HISTORY_FILE = BASE_DIR / "conversation_history.json"
MAX_HISTORY_MESSAGES = 50
MAX_MESSAGE_LENGTH = 3000
MAX_CONTEXT_LENGTH = 60000


def _load_conversation_history() -> List[Dict]:
    """Load conversation history from file."""
    try:
        if CONVERSATION_HISTORY_FILE.exists():
            with open(CONVERSATION_HISTORY_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading conversation history: {e}")
    return []


def _save_conversation_history(history: List[Dict]) -> None:
    """Save conversation history to file."""
    try:
        # Keep only last N messages
        history = history[-MAX_HISTORY_MESSAGES:]
        with open(CONVERSATION_HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving conversation history: {e}")


def _add_to_history(role: str, content: str) -> None:
    """Add a message to conversation history."""
    history = _load_conversation_history()
    tz = pytz.timezone(TIMEZONE)
    timestamp = datetime.now(tz).isoformat()

    history.append({
        "role": role,
        "content": content[:MAX_MESSAGE_LENGTH],
        "timestamp": timestamp
    })
    _save_conversation_history(history)


def _format_history_for_prompt() -> str:
    """Format conversation history - keep it SHORT."""
    history = _load_conversation_history()
    if not history:
        return ""

    # Only last 5 messages, truncated
    recent = history[-5:]

    formatted = "## Recent Chat\n"
    for msg in recent:
        role = "R" if msg["role"] == "user" else "K"
        content = msg["content"][:300]
        if len(msg["content"]) > 300:
            content += "..."
        formatted += f"**{role}:** {content}\n\n"

    return formatted


def _update_session_log(task: str, result: str, success: bool) -> None:
    """Append to SESSION_LOG.md after every response."""
    try:
        tz = pytz.timezone(TIMEZONE)
        timestamp = datetime.now(tz).strftime("%Y-%m-%d %H:%M")

        # Create a short summary of what was done
        task_short = task[:100] + "..." if len(task) > 100 else task
        result_short = result[:200] + "..." if len(result) > 200 else result
        status = "completed" if success else "failed"

        entry = f"\n## {timestamp}\n**Task:** {task_short}\n**Status:** {status}\n**Result:** {result_short}\n"

        # Read existing content
        if SESSION_LOG_FILE.exists():
            content = SESSION_LOG_FILE.read_text()
            lines = content.split("\n")

            # Keep header and last 30 entries (each entry is ~5 lines)
            # Find all ## headers (entries)
            entries = []
            current_entry = []
            header_lines = []
            in_header = True

            for line in lines:
                if line.startswith("## 202"):  # Entry timestamp
                    in_header = False
                    if current_entry:
                        entries.append("\n".join(current_entry))
                    current_entry = [line]
                elif in_header:
                    header_lines.append(line)
                else:
                    current_entry.append(line)

            if current_entry:
                entries.append("\n".join(current_entry))

            # Keep only last 29 entries (making room for new one)
            entries = entries[-29:]

            # Rebuild file
            new_content = "\n".join(header_lines) + "\n" + "\n".join(entries) + entry
            SESSION_LOG_FILE.write_text(new_content)
        else:
            # Create new file
            header = "# SESSION_LOG.md - Rolling Work Log\n\n*Last 30 entries. Oldest entries get removed when adding new ones.*\n\n---\n"
            SESSION_LOG_FILE.write_text(header + entry)

        logger.info(f"Updated SESSION_LOG.md")
    except Exception as e:
        logger.error(f"Error updating session log: {e}")


def _detect_project_mention(text: str) -> Optional[str]:
    """Detect if a project is mentioned in the text."""
    # Common project patterns
    project_patterns = [
        r"true[- ]?podcasts?",
        r"jw[- ]?companion",
        r"nano[- ]?banana",
        r"yt[- ]?automation",
        r"premier[- ]?intelligence",
        r"health[- ]?quest",
        r"keiko",
    ]

    text_lower = text.lower()
    for pattern in project_patterns:
        if re.search(pattern, text_lower):
            return pattern.replace("[- ]?", "-").replace("s?", "")

    # Check for explicit path mentions
    path_match = re.search(re.escape(APPS_DIR) + r"/([a-zA-Z0-9_-]+)", text)
    if path_match:
        return path_match.group(1)

    return None


def _update_active_project(project_name: str, task: str, result: str) -> None:
    """Update ACTIVE_PROJECT.md with current project status."""
    try:
        tz = pytz.timezone(TIMEZONE)
        timestamp = datetime.now(tz).strftime("%Y-%m-%d %H:%M")

        if ACTIVE_PROJECT_FILE.exists():
            content = ACTIVE_PROJECT_FILE.read_text()

            # Add to recent activity section or update status
            activity_entry = f"\n### {timestamp}\n**Task:** {task[:100]}\n**Result:** {result[:300]}\n"

            # Find "## Current Project" section and add activity
            if "## Recent Activity" in content:
                # Add after Recent Activity header
                content = content.replace(
                    "## Recent Activity\n",
                    f"## Recent Activity\n{activity_entry}"
                )
            else:
                # Add new section before Previous Projects
                if "## Previous Projects" in content:
                    content = content.replace(
                        "## Previous Projects",
                        f"## Recent Activity\n{activity_entry}\n---\n\n## Previous Projects"
                    )
                else:
                    content += f"\n\n## Recent Activity\n{activity_entry}"

            ACTIVE_PROJECT_FILE.write_text(content)
            logger.info(f"Updated ACTIVE_PROJECT.md for {project_name}")
    except Exception as e:
        logger.error(f"Error updating active project: {e}")


async def compact_context_if_needed() -> Optional[str]:
    """
    Check if context is getting long and compact it.
    Returns summary if compaction was performed.
    """
    history = _load_conversation_history()
    total_length = sum(len(msg["content"]) for msg in history)

    if total_length < MAX_CONTEXT_LENGTH:
        return None

    # Context is too long - summarize and save to MEMORY.md
    history_text = _format_history_for_prompt()

    # Create a compaction prompt
    compact_prompt = f"""Summarize this conversation history into key points for long-term memory.
Focus on: decisions made, preferences learned, tasks completed, important context.
Keep it under 500 words.

{history_text}"""

    try:
        process = await asyncio.create_subprocess_exec(
            CLAUDE_CLI_PATH,
            "-p", compact_prompt,
            "--dangerously-skip-permissions",
            cwd=APPS_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=60)
        summary = stdout.decode("utf-8", errors="replace").strip()

        if summary:
            # Append to MEMORY.md
            memory_file = WORKSPACE_DIR / "MEMORY.md"
            tz = pytz.timezone(TIMEZONE)
            date = datetime.now(tz).strftime("%Y-%m-%d %H:%M")

            with open(memory_file, "a") as f:
                f.write(f"\n\n---\n\n## Compacted Memory ({date})\n\n{summary}\n")

            # Also save to daily memory file
            daily_file = MEMORY_DIR / f"{datetime.now(tz).strftime('%Y-%m-%d')}.md"
            with open(daily_file, "a") as f:
                f.write(f"\n\n### Context Compaction ({date})\n{summary}\n")

            # Keep last 10 messages after compaction (increased from 5)
            _save_conversation_history(history[-10:])

            return summary
    except Exception as e:
        logger.error(f"Error compacting context: {e}")

    return None


async def execute_claude(
    prompt: str,
    working_dir: Optional[str] = None,
    progress_callback: Optional[Callable] = None,
    project: Optional[Project] = None,
    check_for_swarm: bool = True,
    last_response: Optional[str] = None
) -> Tuple[str, bool]:
    """
    Execute a prompt via Claude Code CLI with project awareness.

    Args:
        prompt: The prompt to send to Claude Code
        working_dir: Optional working directory (defaults to Apps or project path)
        progress_callback: Optional async function to call with progress updates
        project: Optional pre-detected project
        check_for_swarm: Whether to check if this task needs a swarm
        last_response: Last Kiyomi response (for correction detection)

    Returns:
        Tuple of (response_text, success_bool)
    """
    # Check for correction and learn from it
    if last_response:
        was_correction, learned = await process_potential_correction(prompt, last_response)
        if was_correction and learned:
            logger.info(f"Learned from correction: {learned}")

    # Analyze the task for confidence and clarification needs
    analysis = analyze_task(prompt, last_response, current_project=get_current_project_name())

    # Update session with new task
    update_session(
        task=prompt[:200],
        message={"role": "user", "content": prompt[:500]}
    )

    # Check if this task needs a swarm
    if check_for_swarm:
        from swarm import should_spawn_swarm, spawn_swarm, decompose_task
        needs_swarm, subtasks = should_spawn_swarm(prompt)
        if needs_swarm:
            # If no clear subtasks, decompose
            if len(subtasks) == 1 and subtasks[0] == prompt:
                subtasks = await decompose_task(prompt)

            if len(subtasks) > 1:
                if progress_callback:
                    await progress_callback(f"🐝 This looks like a multi-part task. Spawning swarm with {len(subtasks)} agents...")

                swarm = await spawn_swarm(prompt, subtasks, progress_callback)
                # Return early - swarm will handle the rest
                return f"Swarm '{swarm.swarm_id}' spawned with {len(subtasks)} agents. I'll report results when done.", True

    # Detect project from prompt if not provided
    if project is None:
        project = detect_project_from_text(prompt)

    # Set working directory based on project
    if working_dir is None:
        if project:
            working_dir = project.path
            logger.info(f"Using project directory: {project.name}")
        else:
            working_dir = APPS_DIR

    # Update session state with project
    if project:
        set_current_project(project.name.lower().replace(" ", "-"), project.name)
        add_context_note(f"Working on: {project.name}")

    # Check for reference resolution (e.g., "fix it" → current project)
    references = resolve_reference(prompt)
    if references and not project:
        from projects import get_project
        ref_project_id = references.get("project")
        if ref_project_id:
            project = get_project(ref_project_id)
            if project:
                working_dir = project.path
                logger.info(f"Resolved reference to project: {project.name}")

    # Check if we need to compact context first
    compaction = await compact_context_if_needed()
    if compaction:
        logger.info("Context compacted and saved to memory")

    # Save user message to history
    _add_to_history("user", prompt)

    # Check if a skill is relevant and inject it
    skill_name = get_skill_for_task(prompt)
    enhanced_prompt = prompt
    skill_context = ""
    if skill_name:
        enhanced_prompt = inject_skill_context(prompt)
        logger.info(f"Injected skill context: {skill_name}")
        skill_context = f"\n**Active Skill:** {skill_name} (loaded automatically)"

    # Build the context with project awareness
    context = await _build_context(project)
    history = _format_history_for_prompt()

    # Add session continuation context if resuming
    continuation_ctx = get_continuation_context()
    if continuation_ctx:
        context += f"\n\n{continuation_ctx}"

    # Build the prompt
    full_prompt = f"""{context}

{history}
---

You are Kiyomi, Richard's business partner and marketing strategist. You are fun, creative, warm but direct. You're an expert in marketing, YouTube growth, and monetization. You have strong values (clean, honest, no reproach) but keep that private. Think revenue-first. Write in Richard's voice, not corporate speak. Your personality and full context are in the workspace files above.{skill_context}

**Richard:** {enhanced_prompt}
"""

    global _current_process, _current_task_description

    try:
        # Run claude code CLI with full permissions (Richard's personal bot)
        process = await asyncio.create_subprocess_exec(
            CLAUDE_CLI_PATH,
            "-p", full_prompt,
            "--dangerously-skip-permissions",
            cwd=working_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Track for cancellation
        _current_process = process
        _current_task_description = prompt[:100]

        # Stream output with progress updates (minimal - only significant events)
        output_lines = []
        last_update_time = datetime.now()
        last_update_content = ""
        start_time = datetime.now()

        # NO keepalive spam - only send updates for actual progress

        try:
            while True:
                # Check for timeout
                elapsed = (datetime.now() - last_update_time).total_seconds()
                total_elapsed = (datetime.now() - start_time).total_seconds()

                if total_elapsed > TIMEOUT_SECONDS:
                    raise asyncio.TimeoutError()

                # Try to read a line with timeout
                try:
                    line = await asyncio.wait_for(
                        process.stdout.readline(),
                        timeout=5  # Check more frequently
                    )
                except asyncio.TimeoutError:
                    # Check if process is still running
                    if process.returncode is not None:
                        break
                    continue

                if not line:
                    # EOF - process finished
                    break

                line_text = line.decode("utf-8", errors="replace")
                output_lines.append(line_text)

                # Send progress updates so Richard can see what's happening
                if progress_callback:
                    progress = _parse_progress(line_text)
                    if progress and progress != last_update_content:
                        # Send significant events with a 5-second gap to avoid spam
                        if _is_significant_progress(progress) and elapsed > 5:
                            await progress_callback(progress)
                            last_update_time = datetime.now()
                            last_update_content = progress

            # Wait for process to complete
            await asyncio.wait_for(process.wait(), timeout=30)

            # Get any remaining stderr
            stderr_data = await process.stderr.read()
            error = stderr_data.decode("utf-8", errors="replace")

        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            _current_process = None
            _current_task_description = None
            _update_session_log(prompt, "Task timed out after 30 minutes", False)
            logger.warning(f"Task timed out: {prompt[:100]}")
            return "Task took too long. Check if it's still running or try a simpler request.", False

        output = "".join(output_lines)

        if process.returncode != 0 and error:
            logger.error(f"Claude CLI error: {error[:500]}")
            _update_session_log(prompt, f"Error: {error[:200]}", False)

            # Smart escalation - try to handle the error
            await handle_error(
                error_text=error[:500],
                context=f"Task: {prompt[:100]}",
                project=project.name if project else None,
                send_callback=progress_callback,
                auto_fix=True
            )

            return f"Error: {error[:1000]}", False

        # Truncate if too long
        if len(output) > MAX_RESPONSE_LENGTH:
            output = output[:MAX_RESPONSE_LENGTH] + "\n\n... (truncated)"

        result = output.strip() if output.strip() else "✅ Done (no output)"

        # Estimate and log API cost
        input_tokens = estimate_tokens(full_prompt)
        output_tokens = estimate_tokens(result)
        cost = log_api_call(
            model="claude-opus-4-5",  # Kiyomi uses Claude Code which uses Opus
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            project=project.name if project else None,
            task_type="chat"
        )
        logger.debug(f"API call cost: ${cost:.4f}")

        # Check cost alerts
        await check_alerts(progress_callback)

        # Save assistant response to history
        _add_to_history("assistant", result)

        # Update session log
        _update_session_log(prompt, result, True)

        # Update session manager with result
        update_session(
            result=result,
            message={"role": "assistant", "content": result[:500]},
            step_completed=prompt[:100]
        )

        # Check if a project was mentioned and update tracking
        project = _detect_project_mention(prompt) or _detect_project_mention(result)
        if project:
            _update_active_project(project, prompt, result)

        # Clear tracking
        _current_process = None
        _current_task_description = None

        return result, True

    except FileNotFoundError:
        logger.error("Claude CLI not found in PATH")
        return "❌ Claude Code CLI not found. Make sure it's installed.", False
    except Exception as e:
        logger.exception(f"Error executing Claude: {e}")
        _update_session_log(prompt, f"Exception: {str(e)}", False)
        return f"❌ Error: {str(e)}", False


def _parse_progress(line: str) -> Optional[str]:
    """Parse a line of Claude CLI output for progress indicators."""
    line = line.strip()
    if not line:
        return None

    # Detect file operations
    if "Reading" in line or "Read " in line:
        # Extract filename
        match = re.search(r'(?:Reading|Read)\s+[`"]?([^`"\n]+)[`"]?', line)
        if match:
            filename = match.group(1).split('/')[-1]  # Just the filename
            return f"📖 Reading {filename}"

    if "Writing" in line or "Wrote " in line or "Created " in line:
        match = re.search(r'(?:Writing|Wrote|Created)\s+[`"]?([^`"\n]+)[`"]?', line)
        if match:
            filename = match.group(1).split('/')[-1]
            return f"✍️ Writing {filename}"

    if "Editing" in line or "Edit " in line:
        match = re.search(r'(?:Editing|Edit)\s+[`"]?([^`"\n]+)[`"]?', line)
        if match:
            filename = match.group(1).split('/')[-1]
            return f"✏️ Editing {filename}"

    # Detect commands
    if line.startswith("$ ") or line.startswith("> "):
        cmd = line[2:50]  # First 50 chars of command
        return f"⚡ Running: {cmd}..."

    if "npm " in line.lower():
        if "install" in line.lower():
            return "📦 Installing packages..."
        if "run build" in line.lower():
            return "🔨 Building project..."
        if "run dev" in line.lower():
            return "🚀 Starting dev server..."

    if "vercel" in line.lower():
        return "🚀 Deploying to Vercel..."

    if "git " in line.lower():
        if "commit" in line.lower():
            return "📝 Committing changes..."
        if "push" in line.lower():
            return "⬆️ Pushing to remote..."

    # Detect thinking/planning
    if any(word in line.lower() for word in ["thinking", "analyzing", "planning", "checking"]):
        return "🤔 Thinking..."

    # Detect errors
    if "error" in line.lower() or "Error" in line:
        short_error = line[:60]
        return f"⚠️ {short_error}..."

    # Detect success indicators
    if "✓" in line or "success" in line.lower() or "completed" in line.lower():
        return "✅ Step completed"

    return None


def _is_significant_progress(progress: str) -> bool:
    """Check if a progress update is significant enough to send."""
    # Send for all meaningful actions — reading, writing, editing, running, deploying, errors
    significant_prefixes = ["📖", "✍️", "✏️", "⚡", "📦", "🔨", "🚀", "📝", "⬆️", "🤔", "⚠️", "❌", "✅"]
    return any(progress.startswith(p) for p in significant_prefixes)


async def _build_context(project: Optional[Project] = None) -> str:
    """Build context with project awareness and session state."""
    context_parts = []

    # SOUL - Personality and values (ALWAYS load first)
    soul_file = WORKSPACE_DIR / "SOUL.md"
    if soul_file.exists():
        soul_content = soul_file.read_text()
        context_parts.append(soul_content[:3000])

    # IDENTITY - Short, always include
    identity_file = WORKSPACE_DIR / "IDENTITY.md"
    if identity_file.exists():
        context_parts.append(f"## Identity\n{identity_file.read_text()}")

    # USER - Full knowledge about Richard (ALWAYS load)
    user_file = WORKSPACE_DIR / "USER.md"
    if user_file.exists():
        user_content = user_file.read_text()
        context_parts.append(user_content[:2000])

    # MEMORY - Long-term knowledge
    memory_file = WORKSPACE_DIR / "MEMORY.md"
    if memory_file.exists():
        mem_content = memory_file.read_text()
        if len(mem_content) > 2000:
            context_parts.append(f"## Memory (recent)\n{mem_content[-2000:]}")
        else:
            context_parts.append(f"## Memory\n{mem_content}")

    # PROJECT CONTEXT - If we know what project we're working on
    if project:
        context_parts.append(get_project_context(project))

    # SESSION CONTEXT - Recent state
    session_ctx = build_session_context()
    if session_ctx:
        context_parts.append(session_ctx)

    # LEARNED PREFERENCES - From corrections
    preferences = get_preferences_for_context()
    if preferences:
        context_parts.append(preferences)

    # File paths reference - let Claude read on demand
    skills_path = SKILLS_DIR if SKILLS_DIR else "(not configured)"
    env_path = MASTER_ENV_FILE if MASTER_ENV_FILE else "(not configured)"
    context_parts.append(f"""## Key Paths (Read these when needed)
- **Env/API keys:** {env_path}
- **Skills:** {skills_path}
- **Apps:** {APPS_DIR}
- **Error patterns:** {WORKSPACE_DIR / "ERROR_PATTERNS.md"}
- **Projects:** {WORKSPACE_DIR / "PROJECTS.md"}
- **Commitments:** {WORKSPACE_DIR / "COMMITMENTS.md"}""")

    # Communication style reminder
    context_parts.append("""## Communication Style
When fixing errors:
1. Start by briefly stating what you see: "I see the error - [description]"
2. Say what you'll do: "Let me check the code and fix it"
3. Fix it, commit, and deploy if needed
4. Report what you fixed with URL if deployed

After fixing, commit with a good message like: "fix: [what was fixed]"
""")

    return "\n\n".join(context_parts)


async def save_conversation_summary(summary: str) -> bool:
    """
    Manually save a conversation summary to memory files.
    Call this after important conversations or decisions.
    """
    try:
        tz = pytz.timezone(TIMEZONE)
        date = datetime.now(tz).strftime("%Y-%m-%d %H:%M")

        # Append to MEMORY.md
        memory_file = WORKSPACE_DIR / "MEMORY.md"
        with open(memory_file, "a") as f:
            f.write(f"\n\n---\n\n## Session Summary ({date})\n\n{summary}\n")

        # Also save to daily memory file
        daily_file = MEMORY_DIR / f"{datetime.now(tz).strftime('%Y-%m-%d')}.md"
        with open(daily_file, "a") as f:
            f.write(f"\n\n### Session Summary ({date})\n{summary}\n")

        logger.info(f"Saved conversation summary to memory")
        return True
    except Exception as e:
        logger.error(f"Error saving conversation summary: {e}")
        return False


def get_conversation_history() -> List[Dict]:
    """Get the current conversation history (for inspection)."""
    return _load_conversation_history()


def clear_conversation_history() -> bool:
    """Clear conversation history (use with caution)."""
    try:
        _save_conversation_history([])
        return True
    except Exception as e:
        logger.error(f"Error clearing history: {e}")
        return False


async def execute_shell(command: str, working_dir: Optional[str] = None) -> Tuple[str, bool]:
    """
    Execute a shell command directly (for simple tasks).

    Args:
        command: Shell command to execute
        working_dir: Optional working directory

    Returns:
        Tuple of (output, success_bool)
    """
    if working_dir is None:
        working_dir = APPS_DIR

    try:
        process = await asyncio.create_subprocess_shell(
            command,
            cwd=working_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=120  # 2 minutes for shell commands (increased from 1)
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return "⏱️ Command timed out", False

        output = stdout.decode("utf-8", errors="replace")
        error = stderr.decode("utf-8", errors="replace")

        if process.returncode != 0:
            return f"Error (exit {process.returncode}): {error or output}", False

        return output.strip() if output.strip() else "✅ Done", True

    except Exception as e:
        logger.exception(f"Shell execution error: {e}")
        return f"❌ Error: {str(e)}", False


# ============================================
# TASK CANCELLATION
# ============================================

async def cancel_current_task() -> Tuple[bool, str]:
    """
    Cancel the currently running Claude CLI task.
    Returns (success, message).
    """
    global _current_process, _current_task_description

    if _current_process is None:
        return False, "No task currently running"

    task_desc = _current_task_description or "Unknown task"

    try:
        _current_process.kill()
        await _current_process.wait()
        logger.info(f"Cancelled task: {task_desc}")

        _current_process = None
        _current_task_description = None

        return True, f"Cancelled: {task_desc}"
    except Exception as e:
        logger.error(f"Error cancelling task: {e}")
        return False, f"Error cancelling: {str(e)}"


def get_current_task() -> Optional[str]:
    """Get description of currently running task."""
    return _current_task_description


# ============================================
# SUB-AGENT SYSTEM
# ============================================

async def spawn_subagent(
    task_id: str,
    task_description: str,
    working_dir: Optional[str] = None,
    notify_on_complete: bool = True
) -> Tuple[bool, str]:
    """
    Spawn a sub-agent to handle a task in the background.

    Args:
        task_id: Unique identifier for the task
        task_description: What the sub-agent should do
        working_dir: Working directory for the task
        notify_on_complete: Whether to log completion

    Returns:
        Tuple of (success, message)
    """
    global _running_subagents

    if working_dir is None:
        working_dir = APPS_DIR

    # Create log directory
    SUBAGENT_LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Create log file for this sub-agent
    tz = pytz.timezone(TIMEZONE)
    timestamp = datetime.now(tz).strftime("%Y%m%d_%H%M%S")
    log_file = SUBAGENT_LOG_DIR / f"{task_id}_{timestamp}.log"

    # Build prompt for sub-agent
    subagent_prompt = f"""You are a Kiyomi sub-agent running in the background.

TASK ID: {task_id}
TASK: {task_description}

INSTRUCTIONS:
1. Complete this task autonomously
2. Be thorough but efficient
3. Log your progress
4. When done, output a clear summary of what was accomplished

DO NOT ask questions - make reasonable decisions and proceed.
"""

    try:
        # Initialize log file
        with open(log_file, "w") as f:
            f.write(f"Sub-agent started: {datetime.now(tz).isoformat()}\n")
            f.write(f"Task: {task_description}\n")
            f.write("-" * 50 + "\n\n")

        # Open file handle for subprocess (will be closed when process ends)
        log_handle = open(log_file, "a")

        # Spawn the process
        process = await asyncio.create_subprocess_exec(
            CLAUDE_CLI_PATH,
            "-p", subagent_prompt,
            "--dangerously-skip-permissions",
            cwd=working_dir,
            stdout=log_handle,
            stderr=asyncio.subprocess.STDOUT,
        )

        # Store handle for cleanup
        process._log_handle = log_handle

        _running_subagents[task_id] = process
        logger.info(f"Spawned sub-agent {task_id}: {task_description[:50]}...")

        # Start monitoring task
        asyncio.create_task(_monitor_subagent(task_id, process, log_file, notify_on_complete))

        return True, f"Sub-agent '{task_id}' started. Log: {log_file}"

    except Exception as e:
        logger.error(f"Error spawning sub-agent: {e}")
        return False, f"Failed to spawn sub-agent: {str(e)}"


async def _monitor_subagent(
    task_id: str,
    process: asyncio.subprocess.Process,
    log_file: Path,
    notify_on_complete: bool
) -> None:
    """Monitor a sub-agent and handle completion."""
    global _running_subagents

    try:
        # Wait for process to complete (with long timeout for overnight tasks)
        await asyncio.wait_for(process.wait(), timeout=7200)  # 2 hour max

        exit_code = process.returncode
        tz = pytz.timezone(TIMEZONE)
        completion_time = datetime.now(tz).isoformat()

        # Append completion to log
        with open(log_file, "a") as f:
            f.write(f"\n\n" + "-" * 50 + "\n")
            f.write(f"Completed: {completion_time}\n")
            f.write(f"Exit code: {exit_code}\n")

        # Log to daily memory
        from memory_manager import log_to_today
        status = "completed" if exit_code == 0 else "failed"
        log_to_today(f"Sub-agent '{task_id}' {status}. Log: {log_file}")

        logger.info(f"Sub-agent {task_id} completed with exit code {exit_code}")

    except asyncio.TimeoutError:
        process.kill()
        logger.warning(f"Sub-agent {task_id} timed out after 2 hours")
        from memory_manager import log_to_today
        log_to_today(f"Sub-agent '{task_id}' timed out after 2 hours")

    except Exception as e:
        logger.error(f"Error monitoring sub-agent {task_id}: {e}")

    finally:
        # Close log file handle if it exists
        if hasattr(process, '_log_handle'):
            try:
                process._log_handle.close()
            except:
                pass
        # Remove from tracking
        _running_subagents.pop(task_id, None)


async def get_subagent_status(task_id: str) -> Optional[Dict]:
    """Get status of a sub-agent."""
    if task_id not in _running_subagents:
        # Check if there's a log file
        log_files = list(SUBAGENT_LOG_DIR.glob(f"{task_id}_*.log"))
        if log_files:
            latest_log = max(log_files, key=lambda p: p.stat().st_mtime)
            content = latest_log.read_text()
            return {
                "task_id": task_id,
                "status": "completed" if "Completed:" in content else "unknown",
                "log_file": str(latest_log),
                "log_tail": content[-1000:] if len(content) > 1000 else content
            }
        return None

    return {
        "task_id": task_id,
        "status": "running",
        "pid": _running_subagents[task_id].pid
    }


def list_running_subagents() -> List[Dict]:
    """List all currently running sub-agents."""
    return [
        {"task_id": tid, "pid": proc.pid}
        for tid, proc in _running_subagents.items()
    ]


async def cancel_subagent(task_id: str) -> Tuple[bool, str]:
    """Cancel a running sub-agent."""
    if task_id not in _running_subagents:
        return False, f"No sub-agent with ID '{task_id}' is running"

    try:
        _running_subagents[task_id].kill()
        await _running_subagents[task_id].wait()
        _running_subagents.pop(task_id, None)
        logger.info(f"Cancelled sub-agent {task_id}")
        return True, f"Sub-agent '{task_id}' cancelled"
    except Exception as e:
        return False, f"Error cancelling sub-agent: {str(e)}"
