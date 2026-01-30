"""
Kiyomi Swarm Intelligence - Auto-spawn and coordinate agent teams

Features:
- Analyze tasks to determine if multiple agents are needed
- Auto-spawn coordinated agent teams
- Aggregate results from multiple agents
- Report consolidated results
"""
import asyncio
import logging
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Callable, Tuple
from enum import Enum

import pytz
from config import BASE_DIR, TIMEZONE, CLAUDE_CLI_PATH, APPS_DIR

logger = logging.getLogger(__name__)

# Swarm configuration
SWARM_LOG_DIR = BASE_DIR / "swarm_logs"
SWARM_STATE_FILE = BASE_DIR / "swarm_state.json"
MAX_CONCURRENT_AGENTS = 5
AGENT_TIMEOUT = 3600  # 1 hour per agent


class TaskComplexity(Enum):
    SIMPLE = "simple"       # Single agent can handle
    MODERATE = "moderate"   # 2-3 agents might help
    COMPLEX = "complex"     # Needs full swarm


@dataclass
class SwarmAgent:
    """Represents a single agent in the swarm."""
    agent_id: str
    task: str
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    process: Optional[asyncio.subprocess.Process] = None
    log_file: Optional[Path] = None


@dataclass
class SwarmTask:
    """Represents a coordinated swarm task."""
    swarm_id: str
    master_task: str
    subtasks: List[str] = field(default_factory=list)
    agents: Dict[str, SwarmAgent] = field(default_factory=dict)
    status: str = "planning"  # planning, running, aggregating, completed, failed
    aggregated_result: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(pytz.timezone(TIMEZONE)))


# Global swarm state
_active_swarms: Dict[str, SwarmTask] = {}


def analyze_task_complexity(task: str) -> Tuple[TaskComplexity, List[str]]:
    """
    Analyze a task to determine if it needs multiple agents.
    Returns (complexity, suggested_subtasks).
    """
    task_lower = task.lower()

    # Patterns that suggest parallel work
    parallel_patterns = [
        r"all\s+(projects|apps|sites)",
        r"each\s+(project|app|site)",
        r"multiple\s+(things|tasks|items)",
        r"and\s+also",
        r"as\s+well\s+as",
        r"in\s+parallel",
        r"at\s+the\s+same\s+time",
        r"batch\s+",
        r"all\s+at\s+once",
    ]

    # Complex task patterns
    complex_patterns = [
        r"refactor\s+(?:the\s+)?entire",
        r"update\s+all",
        r"check\s+all",
        r"deploy\s+(?:all|multiple|every)",
        r"migrate\s+",
        r"comprehensive\s+",
        r"full\s+(?:audit|review|scan)",
        r"across\s+all",
    ]

    # Check for parallel indicators
    needs_parallel = any(re.search(p, task_lower) for p in parallel_patterns)
    is_complex = any(re.search(p, task_lower) for p in complex_patterns)

    # Suggest subtasks based on task content
    subtasks = []

    # Check for explicit project mentions
    from projects import list_projects
    projects = list_projects()
    mentioned_projects = []

    for project in projects:
        project_name_lower = project.name.lower()
        if project_name_lower in task_lower or project_name_lower.replace(" ", "-") in task_lower:
            mentioned_projects.append(project.name)

    # If "all projects" or similar, create subtask per project
    if re.search(r"all\s+(projects|apps|sites)", task_lower):
        for project in projects:
            subtasks.append(f"For {project.name}: {task}")

    # Determine complexity
    if len(subtasks) > 3 or is_complex:
        return TaskComplexity.COMPLEX, subtasks
    elif needs_parallel or len(subtasks) > 1:
        return TaskComplexity.MODERATE, subtasks
    else:
        return TaskComplexity.SIMPLE, []


def should_spawn_swarm(task: str) -> Tuple[bool, List[str]]:
    """
    Determine if a task should spawn a swarm.
    Returns (should_spawn, subtasks).
    """
    complexity, subtasks = analyze_task_complexity(task)

    if complexity == TaskComplexity.SIMPLE:
        return False, []

    # If we identified specific subtasks, use those
    if subtasks:
        return True, subtasks[:MAX_CONCURRENT_AGENTS]  # Limit agents

    # For moderate/complex without clear subtasks, suggest decomposition
    if complexity == TaskComplexity.COMPLEX:
        # Let the swarm coordinator decompose
        return True, [task]  # Single task that will be decomposed

    return False, []


async def decompose_task(task: str) -> List[str]:
    """
    Use Claude to decompose a complex task into subtasks.
    """
    decompose_prompt = f"""Break down this task into 2-5 independent subtasks that can be done in parallel.
Each subtask should be self-contained and accomplishable by a single agent.

TASK: {task}

Return ONLY a JSON array of subtask strings. Example:
["Subtask 1 description", "Subtask 2 description"]

If the task cannot be parallelized, return the original task in an array:
["{task}"]"""

    try:
        process = await asyncio.create_subprocess_exec(
            CLAUDE_CLI_PATH,
            "-p", decompose_prompt,
            "--dangerously-skip-permissions",
            cwd=APPS_DIR,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=60)
        output = stdout.decode("utf-8", errors="replace").strip()

        # Try to parse JSON array
        # Find JSON array in output
        match = re.search(r'\[.*?\]', output, re.DOTALL)
        if match:
            subtasks = json.loads(match.group())
            if isinstance(subtasks, list) and all(isinstance(s, str) for s in subtasks):
                return subtasks[:MAX_CONCURRENT_AGENTS]

        # Fallback: return original task
        return [task]

    except Exception as e:
        logger.error(f"Error decomposing task: {e}")
        return [task]


async def spawn_swarm(
    master_task: str,
    subtasks: List[str],
    send_callback: Optional[Callable] = None
) -> SwarmTask:
    """
    Spawn a coordinated swarm of agents.

    Args:
        master_task: The original task
        subtasks: List of subtasks to parallelize
        send_callback: Function to send status updates

    Returns:
        SwarmTask object
    """
    tz = pytz.timezone(TIMEZONE)
    timestamp = datetime.now(tz).strftime("%Y%m%d_%H%M%S")
    swarm_id = f"swarm_{timestamp}"

    # Create swarm log directory
    SWARM_LOG_DIR.mkdir(parents=True, exist_ok=True)
    swarm_dir = SWARM_LOG_DIR / swarm_id
    swarm_dir.mkdir(exist_ok=True)

    # Create swarm task
    swarm = SwarmTask(
        swarm_id=swarm_id,
        master_task=master_task,
        subtasks=subtasks,
        status="running"
    )

    if send_callback:
        await send_callback(f"🐝 **Spawning Swarm** ({len(subtasks)} agents)\n\n" +
                          "\n".join(f"• Agent {i+1}: {t[:50]}..." for i, t in enumerate(subtasks)))

    # Spawn agents
    for i, subtask in enumerate(subtasks):
        agent_id = f"agent_{i+1}"
        log_file = swarm_dir / f"{agent_id}.log"

        agent = SwarmAgent(
            agent_id=agent_id,
            task=subtask,
            log_file=log_file
        )
        swarm.agents[agent_id] = agent

        # Spawn agent process
        asyncio.create_task(_run_swarm_agent(swarm, agent, send_callback))

    # Store swarm
    _active_swarms[swarm_id] = swarm
    _save_swarm_state()

    # Start aggregation monitor
    asyncio.create_task(_monitor_swarm(swarm, send_callback))

    return swarm


async def _run_swarm_agent(
    swarm: SwarmTask,
    agent: SwarmAgent,
    send_callback: Optional[Callable]
) -> None:
    """Run a single agent in the swarm."""
    tz = pytz.timezone(TIMEZONE)
    agent.status = "running"
    agent.started_at = datetime.now(tz)

    # Build agent prompt
    agent_prompt = f"""You are Swarm Agent {agent.agent_id}, part of a coordinated team.

MASTER TASK: {swarm.master_task}

YOUR SPECIFIC TASK: {agent.task}

INSTRUCTIONS:
1. Complete your specific task independently
2. Be thorough but efficient
3. Output a clear summary of what you accomplished
4. If you encounter blockers, note them but continue with what you can do

DO NOT ask questions - make reasonable decisions and proceed."""

    log_handle = None
    try:
        with open(agent.log_file, "w") as f:
            f.write(f"Agent {agent.agent_id} started: {agent.started_at.isoformat()}\n")
            f.write(f"Task: {agent.task}\n")
            f.write("-" * 50 + "\n\n")

        log_handle = open(agent.log_file, "a")

        process = await asyncio.create_subprocess_exec(
            CLAUDE_CLI_PATH,
            "-p", agent_prompt,
            "--dangerously-skip-permissions",
            cwd=APPS_DIR,
            stdout=log_handle,
            stderr=asyncio.subprocess.STDOUT,
        )

        agent.process = process

        try:
            await asyncio.wait_for(process.wait(), timeout=AGENT_TIMEOUT)

            # Close log before reading
            log_handle.close()
            log_handle = None
            agent.result = agent.log_file.read_text()
            agent.status = "completed" if process.returncode == 0 else "failed"

        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            agent.status = "failed"
            agent.result = "Agent timed out"

        agent.completed_at = datetime.now(tz)

    except Exception as e:
        logger.error(f"Error running swarm agent {agent.agent_id}: {e}")
        agent.status = "failed"
        agent.result = f"Error: {str(e)}"
        agent.completed_at = datetime.now(tz)

    finally:
        if log_handle is not None:
            try:
                log_handle.close()
            except Exception:
                pass


async def _monitor_swarm(swarm: SwarmTask, send_callback: Optional[Callable]) -> None:
    """Monitor swarm progress and aggregate results when done."""
    tz = pytz.timezone(TIMEZONE)

    while True:
        await asyncio.sleep(5)  # Check every 5 seconds

        # Check agent statuses
        completed = sum(1 for a in swarm.agents.values() if a.status in ["completed", "failed"])
        total = len(swarm.agents)

        if completed == total:
            break

    # All agents done - aggregate results
    swarm.status = "aggregating"

    if send_callback:
        await send_callback(f"🐝 **Swarm Complete** - Aggregating results from {total} agents...")

    # Aggregate results
    aggregated = await _aggregate_swarm_results(swarm)
    swarm.aggregated_result = aggregated
    swarm.status = "completed"

    _save_swarm_state()

    if send_callback:
        # Send summary
        success_count = sum(1 for a in swarm.agents.values() if a.status == "completed")
        fail_count = total - success_count

        summary = f"🐝 **Swarm Report**\n\n"
        summary += f"**Task:** {swarm.master_task[:100]}...\n"
        summary += f"**Agents:** {success_count} succeeded, {fail_count} failed\n\n"
        summary += f"**Result:**\n{aggregated[:2000]}"

        if len(aggregated) > 2000:
            summary += f"\n\n... (truncated, full log in {SWARM_LOG_DIR / swarm.swarm_id})"

        await send_callback(summary)


async def _aggregate_swarm_results(swarm: SwarmTask) -> str:
    """Aggregate results from all swarm agents."""
    # Collect results
    results_text = ""
    for agent_id, agent in swarm.agents.items():
        results_text += f"\n\n=== {agent_id} ({agent.status}) ===\n"
        results_text += f"Task: {agent.task}\n"
        results_text += f"Result: {agent.result[:1000] if agent.result else 'No output'}\n"

    # Use Claude to summarize
    aggregate_prompt = f"""Summarize the results from these parallel agents into a cohesive report.

MASTER TASK: {swarm.master_task}

AGENT RESULTS:
{results_text}

Provide a clear, organized summary of:
1. What was accomplished
2. Any issues encountered
3. Overall status
4. Next steps if any"""

    try:
        process = await asyncio.create_subprocess_exec(
            CLAUDE_CLI_PATH,
            "-p", aggregate_prompt,
            "--dangerously-skip-permissions",
            cwd=APPS_DIR,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=120)
        return stdout.decode("utf-8", errors="replace").strip()

    except Exception as e:
        logger.error(f"Error aggregating swarm results: {e}")
        return results_text  # Return raw results on failure


def get_active_swarms() -> List[Dict]:
    """Get list of active swarms."""
    return [
        {
            "swarm_id": s.swarm_id,
            "master_task": s.master_task[:50],
            "status": s.status,
            "agents": len(s.agents),
            "completed": sum(1 for a in s.agents.values() if a.status in ["completed", "failed"]),
            "created_at": s.created_at.isoformat()
        }
        for s in _active_swarms.values()
    ]


def get_swarm_status(swarm_id: str) -> Optional[Dict]:
    """Get detailed status of a swarm."""
    if swarm_id not in _active_swarms:
        return None

    swarm = _active_swarms[swarm_id]
    return {
        "swarm_id": swarm.swarm_id,
        "master_task": swarm.master_task,
        "status": swarm.status,
        "agents": {
            aid: {
                "task": a.task[:50],
                "status": a.status,
                "started_at": a.started_at.isoformat() if a.started_at else None,
                "completed_at": a.completed_at.isoformat() if a.completed_at else None
            }
            for aid, a in swarm.agents.items()
        },
        "aggregated_result": swarm.aggregated_result[:500] if swarm.aggregated_result else None
    }


def _save_swarm_state() -> None:
    """Save swarm state to file."""
    try:
        state = {
            swarm_id: {
                "swarm_id": s.swarm_id,
                "master_task": s.master_task,
                "subtasks": s.subtasks,
                "status": s.status,
                "created_at": s.created_at.isoformat(),
                "aggregated_result": s.aggregated_result
            }
            for swarm_id, s in _active_swarms.items()
        }

        with open(SWARM_STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)

    except Exception as e:
        logger.error(f"Error saving swarm state: {e}")


def _load_swarm_state() -> None:
    """Load swarm state from file."""
    global _active_swarms

    try:
        if SWARM_STATE_FILE.exists():
            with open(SWARM_STATE_FILE) as f:
                state = json.load(f)

            for swarm_id, data in state.items():
                # Only load completed swarms (for history)
                if data.get("status") == "completed":
                    swarm = SwarmTask(
                        swarm_id=data["swarm_id"],
                        master_task=data["master_task"],
                        subtasks=data.get("subtasks", []),
                        status=data["status"],
                        aggregated_result=data.get("aggregated_result"),
                        created_at=datetime.fromisoformat(data["created_at"])
                    )
                    _active_swarms[swarm_id] = swarm

    except Exception as e:
        logger.error(f"Error loading swarm state: {e}")


# Load state on module import
_load_swarm_state()
