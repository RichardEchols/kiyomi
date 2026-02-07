"""
Kiyomi Gateway — Agent-to-Agent Communication Layer

Enables multiple Kiyomi instances (Kiyomi, Arianna, Brock) to coordinate
across machines on the same local network.

Architecture:
  - Each instance runs an HTTP API on its existing server (port 8765)
  - Agent registry defines the team (who, what role, how to reach them)
  - Agents delegate tasks via HTTP POST to each other
  - Results flow back via callback URL
  - Claude Code CLI executes delegated tasks locally

No WebSocket gateway needed — direct peer-to-peer over local WiFi.
"""
import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Dict, List, Callable, Any
from urllib.request import Request, urlopen
from urllib.error import URLError

logger = logging.getLogger("kiyomi.gateway")

# Agent registry lives in ~/.kiyomi/agents.json
CONFIG_DIR = Path.home() / ".kiyomi"
AGENTS_FILE = CONFIG_DIR / "agents.json"
TASK_LOG_FILE = CONFIG_DIR / "agent_tasks.json"


@dataclass
class AgentInfo:
    """Represents a team member."""
    agent_id: str
    name: str
    role: str
    emoji: str
    host: str
    port: int = 8765
    domains: list = field(default_factory=list)

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AgentTask:
    """A task sent between agents."""
    task_id: str
    from_agent: str
    to_agent: str
    prompt: str
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)


class AgentRegistry:
    """Manages the team of Kiyomi agents."""

    def __init__(self):
        self.self_agent: Optional[AgentInfo] = None
        self.team: Dict[str, AgentInfo] = {}
        self._loaded = False

    def load(self):
        """Load agent registry from ~/.kiyomi/agents.json"""
        if not AGENTS_FILE.exists():
            logger.info("No agents.json found — running solo")
            self._loaded = True
            return

        try:
            with open(AGENTS_FILE) as f:
                data = json.load(f)

            # Load self
            self_data = data.get("self", {})
            if self_data:
                self.self_agent = AgentInfo(**self_data)

            # Load team
            for agent_data in data.get("team", []):
                agent = AgentInfo(**agent_data)
                self.team[agent.agent_id] = agent

            self._loaded = True
            team_names = [a.name for a in self.team.values()]
            logger.info(f"Agent registry loaded: I am {self.self_agent.name if self.self_agent else 'unknown'}. "
                        f"Team: {', '.join(team_names) if team_names else 'none'}")
        except Exception as e:
            logger.error(f"Failed to load agents.json: {e}")
            self._loaded = True

    def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """Get a team member by ID."""
        return self.team.get(agent_id)

    def find_agent_for_domain(self, message: str) -> Optional[AgentInfo]:
        """Find the best agent to handle a message based on domain keywords."""
        msg_lower = message.lower()
        for agent in self.team.values():
            for domain in agent.domains:
                if domain.lower() in msg_lower:
                    return agent
        return None

    def get_team_prompt(self) -> str:
        """Generate team awareness text for the system prompt."""
        if not self.self_agent or not self.team:
            return ""

        lines = [
            "\n## Your Team",
            f"You are {self.self_agent.name} {self.self_agent.emoji}.",
            f"Your role: {self.self_agent.role}\n",
            "Your teammates:"
        ]
        for agent in self.team.values():
            domains_str = ", ".join(agent.domains[:5]) if agent.domains else agent.role
            lines.append(f"- **{agent.name}** {agent.emoji} — {agent.role} (handles: {domains_str})")

        lines.extend([
            "",
            "## Delegation Rules",
            "- If a request falls outside your role, delegate to the right teammate.",
            "- To delegate, start your response with: @agent_id: [what you need them to do]",
            "- Example: '@arianna: Draft a launch email for the new trading dashboard'",
            "- If you're unsure who should handle it, handle it yourself.",
            "- NEVER delegate tasks within your own domain.",
            "- When you receive a delegated task, execute it fully and return the result.",
        ])

        return "\n".join(lines)

    def list_agents(self) -> List[dict]:
        """List all agents for display."""
        agents = []
        if self.self_agent:
            agents.append({**self.self_agent.to_dict(), "is_self": True})
        for agent in self.team.values():
            agents.append({**agent.to_dict(), "is_self": False})
        return agents


class AgentCommunicator:
    """Handles sending tasks to and receiving tasks from other agents."""

    def __init__(self, registry: AgentRegistry):
        self.registry = registry
        self._pending_tasks: Dict[str, AgentTask] = {}
        self._task_results: Dict[str, asyncio.Future] = {}
        self._execute_fn: Optional[Callable] = None
        self._notify_fn: Optional[Callable] = None

    def set_execute_fn(self, fn: Callable):
        """Set the function to execute delegated tasks (Claude Code CLI)."""
        self._execute_fn = fn

    def set_notify_fn(self, fn: Callable):
        """Set the function to notify the user of results (Telegram)."""
        self._notify_fn = fn

    async def send_task(self, to_agent_id: str, prompt: str, timeout: float = 300) -> dict:
        """Send a task to another agent and wait for the result."""
        agent = self.registry.get_agent(to_agent_id)
        if not agent:
            return {"status": "error", "error": f"Unknown agent: {to_agent_id}"}

        task_id = str(uuid.uuid4())[:8]
        task = AgentTask(
            task_id=task_id,
            from_agent=self.registry.self_agent.agent_id if self.registry.self_agent else "unknown",
            to_agent=to_agent_id,
            prompt=prompt,
        )
        self._pending_tasks[task_id] = task

        # Create a future for the result
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._task_results[task_id] = future

        # Send task via HTTP POST
        callback_url = ""
        if self.registry.self_agent:
            callback_url = f"http://{self.registry.self_agent.host}:{self.registry.self_agent.port}/api/agent/result"

        payload = json.dumps({
            "task_id": task_id,
            "from_agent": task.from_agent,
            "prompt": prompt,
            "callback_url": callback_url,
        }).encode()

        try:
            url = f"{agent.base_url}/api/agent/task"
            logger.info(f"Sending task {task_id} to {agent.name}: {prompt[:100]}...")

            # Use asyncio to not block
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._http_post, url, payload
            )

            if result.get("status") == "accepted":
                task.status = "running"
                # Wait for the result callback
                try:
                    response = await asyncio.wait_for(future, timeout=timeout)
                    task.status = "completed"
                    task.result = response.get("result", "")
                    task.completed_at = time.time()
                    self._log_task(task)
                    return response
                except asyncio.TimeoutError:
                    task.status = "failed"
                    task.result = f"Timed out after {timeout}s"
                    self._log_task(task)
                    return {"status": "error", "error": f"Task timed out after {timeout}s"}
            else:
                task.status = "failed"
                task.result = result.get("error", "Agent rejected the task")
                self._log_task(task)
                return result

        except Exception as e:
            task.status = "failed"
            task.result = str(e)
            self._log_task(task)
            return {"status": "error", "error": f"Could not reach {agent.name}: {str(e)}"}
        finally:
            self._task_results.pop(task_id, None)

    def handle_result(self, task_id: str, result: str):
        """Handle a result callback from another agent."""
        if task_id in self._task_results:
            future = self._task_results[task_id]
            if not future.done():
                future.set_result({"status": "completed", "result": result})
            logger.info(f"Received result for task {task_id}")

    async def handle_incoming_task(self, task_data: dict) -> dict:
        """Handle a task sent to us by another agent."""
        task_id = task_data.get("task_id", str(uuid.uuid4())[:8])
        from_agent = task_data.get("from_agent", "unknown")
        prompt = task_data.get("prompt", "")
        callback_url = task_data.get("callback_url", "")

        logger.info(f"Received task {task_id} from {from_agent}: {prompt[:100]}...")

        if not self._execute_fn:
            return {"status": "error", "error": "No execution function configured"}

        # Execute the task asynchronously
        asyncio.create_task(
            self._execute_and_callback(task_id, from_agent, prompt, callback_url)
        )

        return {"status": "accepted", "task_id": task_id}

    async def _execute_and_callback(self, task_id: str, from_agent: str, prompt: str, callback_url: str):
        """Execute a task and send the result back."""
        try:
            result = await self._execute_fn(prompt)

            # Send result back via callback
            if callback_url:
                payload = json.dumps({
                    "task_id": task_id,
                    "from_agent": self.registry.self_agent.agent_id if self.registry.self_agent else "unknown",
                    "result": result,
                }).encode()

                await asyncio.get_event_loop().run_in_executor(
                    None, self._http_post, callback_url, payload
                )
                logger.info(f"Sent result for task {task_id} back to {from_agent}")

            # Also notify the user on Telegram
            if self._notify_fn:
                sender = self.registry.get_agent(from_agent)
                sender_name = sender.name if sender else from_agent
                await self._notify_fn(
                    f"Completed task from {sender_name}:\n\n{result[:3000]}"
                )

        except Exception as e:
            logger.error(f"Task {task_id} execution failed: {e}")
            if callback_url:
                payload = json.dumps({
                    "task_id": task_id,
                    "from_agent": self.registry.self_agent.agent_id if self.registry.self_agent else "unknown",
                    "result": f"Error: {str(e)}",
                }).encode()
                try:
                    await asyncio.get_event_loop().run_in_executor(
                        None, self._http_post, callback_url, payload
                    )
                except Exception:
                    pass

    async def check_agent_status(self, agent_id: str) -> dict:
        """Check if an agent is online."""
        agent = self.registry.get_agent(agent_id)
        if not agent:
            return {"agent_id": agent_id, "status": "unknown"}

        try:
            url = f"{agent.base_url}/api/agent/status"
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._http_get, url
            )
            return {"agent_id": agent_id, "name": agent.name, "status": "online", **result}
        except Exception:
            return {"agent_id": agent_id, "name": agent.name, "status": "offline"}

    async def check_all_agents(self) -> List[dict]:
        """Check status of all team agents."""
        tasks = [self.check_agent_status(aid) for aid in self.registry.team]
        return await asyncio.gather(*tasks)

    @staticmethod
    def _http_post(url: str, payload: bytes) -> dict:
        """Synchronous HTTP POST (run in executor)."""
        req = Request(url, data=payload, headers={"Content-Type": "application/json"})
        req.method = "POST"
        try:
            with urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except URLError as e:
            raise ConnectionError(f"POST {url} failed: {e}")

    @staticmethod
    def _http_get(url: str) -> dict:
        """Synchronous HTTP GET (run in executor)."""
        req = Request(url)
        try:
            with urlopen(req, timeout=5) as resp:
                return json.loads(resp.read())
        except URLError as e:
            raise ConnectionError(f"GET {url} failed: {e}")

    def _log_task(self, task: AgentTask):
        """Log completed/failed tasks to disk."""
        try:
            log = []
            if TASK_LOG_FILE.exists():
                with open(TASK_LOG_FILE) as f:
                    log = json.load(f)
            log.append(task.to_dict())
            # Keep last 200 tasks
            if len(log) > 200:
                log = log[-200:]
            with open(TASK_LOG_FILE, "w") as f:
                json.dump(log, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not log task: {e}")


# --- Delegation Parser ---

def parse_delegation(response: str, registry: AgentRegistry) -> Optional[tuple]:
    """Check if an AI response contains a delegation directive.

    Looks for patterns like:
        @arianna: Draft a launch email for the app
        @brock: Check the current BTC price

    Returns (agent_id, task_prompt) or None.
    """
    import re
    for agent_id in registry.team:
        # Match @agent_id: or @agent_name: at the start of the response
        agent = registry.team[agent_id]
        patterns = [
            rf"^@{re.escape(agent_id)}:\s*(.+)",
            rf"^@{re.escape(agent.name.lower())}:\s*(.+)",
        ]
        for pattern in patterns:
            match = re.match(pattern, response.strip(), re.IGNORECASE | re.DOTALL)
            if match:
                return (agent_id, match.group(1).strip())
    return None


def parse_user_delegation(message: str, registry: AgentRegistry) -> Optional[tuple]:
    """Check if a user message explicitly delegates to an agent.

    Looks for patterns like:
        @arianna draft a launch email
        hey arianna, can you check the analytics?
        arianna: make me a thumbnail

    Returns (agent_id, task_prompt) or None.
    """
    import re
    msg_lower = message.lower().strip()

    for agent_id, agent in registry.team.items():
        name_lower = agent.name.lower()
        patterns = [
            # @agent_id message
            (rf"^@{re.escape(agent_id)}\s+(.+)", re.IGNORECASE | re.DOTALL),
            # @agent_name message
            (rf"^@{re.escape(name_lower)}\s+(.+)", re.IGNORECASE | re.DOTALL),
            # agent_name: message
            (rf"^{re.escape(name_lower)}:\s*(.+)", re.IGNORECASE | re.DOTALL),
            # hey agent_name, message
            (rf"^(?:hey|yo|ask)\s+{re.escape(name_lower)}[,:]?\s+(.+)", re.IGNORECASE | re.DOTALL),
            # tell agent_name to message
            (rf"^tell\s+{re.escape(name_lower)}\s+(?:to\s+)?(.+)", re.IGNORECASE | re.DOTALL),
        ]
        for pattern, flags in patterns:
            match = re.match(pattern, message.strip(), flags)
            if match:
                return (agent_id, match.group(1).strip())
    return None


# --- Global instances ---
_registry: Optional[AgentRegistry] = None
_communicator: Optional[AgentCommunicator] = None


def init_gateway() -> tuple:
    """Initialize the gateway. Returns (registry, communicator)."""
    global _registry, _communicator

    _registry = AgentRegistry()
    _registry.load()

    _communicator = AgentCommunicator(_registry)

    return _registry, _communicator


def get_registry() -> Optional[AgentRegistry]:
    return _registry


def get_communicator() -> Optional[AgentCommunicator]:
    return _communicator
