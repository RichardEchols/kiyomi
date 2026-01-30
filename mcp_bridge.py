"""
Kiyomi MCP Bridge - Connect to Claude Desktop MCP servers

Features:
- Discover available MCP servers from Claude Desktop config
- Route requests to appropriate MCP servers
- Bring MCP capabilities to Telegram
"""
import asyncio
import json
import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple

logger = logging.getLogger(__name__)

# Claude Desktop config location
CLAUDE_CONFIG_PATH = Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"

# MCP server cache
_mcp_servers: Dict[str, Dict] = {}
_mcp_initialized = False


def load_mcp_config() -> Dict[str, Any]:
    """Load MCP server configuration from Claude Desktop."""
    global _mcp_servers, _mcp_initialized

    try:
        if not CLAUDE_CONFIG_PATH.exists():
            logger.info("Claude Desktop config not found")
            return {}

        with open(CLAUDE_CONFIG_PATH) as f:
            config = json.load(f)

        _mcp_servers = config.get("mcpServers", {})
        _mcp_initialized = True

        logger.info(f"Loaded {len(_mcp_servers)} MCP servers from Claude Desktop")
        return _mcp_servers

    except Exception as e:
        logger.error(f"Error loading MCP config: {e}")
        return {}


def get_available_mcps() -> List[Dict[str, str]]:
    """Get list of available MCP servers."""
    if not _mcp_initialized:
        load_mcp_config()

    return [
        {
            "name": name,
            "command": config.get("command", "unknown"),
            "description": _get_mcp_description(name)
        }
        for name, config in _mcp_servers.items()
    ]


def _get_mcp_description(name: str) -> str:
    """Get a human-readable description for an MCP server."""
    descriptions = {
        "filesystem": "Read and write files",
        "github": "GitHub operations (repos, issues, PRs)",
        "git": "Git version control",
        "postgres": "PostgreSQL database",
        "sqlite": "SQLite database",
        "brave-search": "Web search via Brave",
        "fetch": "Fetch web pages",
        "memory": "Persistent memory storage",
        "puppeteer": "Browser automation",
        "slack": "Slack messaging",
        "google-drive": "Google Drive files",
        "google-maps": "Google Maps/Places",
        "sentry": "Sentry error tracking",
        "raygun": "Raygun error tracking",
        "sequential-thinking": "Step-by-step reasoning",
    }

    # Check for partial matches
    name_lower = name.lower()
    for key, desc in descriptions.items():
        if key in name_lower:
            return desc

    return "MCP tool server"


async def call_mcp_server(
    server_name: str,
    method: str,
    params: Optional[Dict] = None
) -> Tuple[bool, Any]:
    """
    Call an MCP server method.

    This is a simplified interface - in practice, MCP servers
    communicate via stdio and JSON-RPC.

    Returns (success, result_or_error)
    """
    if not _mcp_initialized:
        load_mcp_config()

    if server_name not in _mcp_servers:
        return False, f"MCP server '{server_name}' not found"

    config = _mcp_servers[server_name]
    command = config.get("command")
    args = config.get("args", [])

    if not command:
        return False, f"No command configured for {server_name}"

    # Build JSON-RPC request
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or {}
    }

    try:
        # Start the MCP server process
        full_command = [command] + args

        process = await asyncio.create_subprocess_exec(
            *full_command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Send request
        request_bytes = (json.dumps(request) + "\n").encode()
        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=request_bytes),
            timeout=30
        )

        # Parse response
        if stdout:
            response = json.loads(stdout.decode())
            if "result" in response:
                return True, response["result"]
            elif "error" in response:
                return False, response["error"].get("message", "Unknown error")

        return False, stderr.decode() if stderr else "No response"

    except asyncio.TimeoutError:
        return False, "MCP call timed out"
    except json.JSONDecodeError as e:
        return False, f"Invalid response: {e}"
    except Exception as e:
        return False, f"MCP call failed: {e}"


async def list_mcp_tools(server_name: str) -> Tuple[bool, List[Dict]]:
    """List available tools from an MCP server."""
    success, result = await call_mcp_server(server_name, "tools/list")

    if success and isinstance(result, dict):
        return True, result.get("tools", [])

    return success, result


# ============================================
# HIGH-LEVEL MCP INTEGRATIONS
# ============================================

async def mcp_read_file(path: str) -> Tuple[bool, str]:
    """Read a file via filesystem MCP."""
    # Find filesystem MCP
    for name in _mcp_servers:
        if "filesystem" in name.lower():
            return await call_mcp_server(name, "read_file", {"path": path})
    return False, "Filesystem MCP not available"


async def mcp_github_issue(repo: str, issue_number: int) -> Tuple[bool, Dict]:
    """Get GitHub issue via github MCP."""
    for name in _mcp_servers:
        if "github" in name.lower():
            return await call_mcp_server(
                name,
                "get_issue",
                {"owner": repo.split("/")[0], "repo": repo.split("/")[1], "issue_number": issue_number}
            )
    return False, "GitHub MCP not available"


async def mcp_web_search(query: str) -> Tuple[bool, List]:
    """Search the web via brave-search MCP."""
    for name in _mcp_servers:
        if "brave" in name.lower() or "search" in name.lower():
            return await call_mcp_server(name, "brave_web_search", {"query": query})
    return False, "Search MCP not available"


async def mcp_fetch_url(url: str) -> Tuple[bool, str]:
    """Fetch a URL via fetch MCP."""
    for name in _mcp_servers:
        if "fetch" in name.lower():
            return await call_mcp_server(name, "fetch", {"url": url})
    return False, "Fetch MCP not available"


# ============================================
# MCP ROUTING FOR KEIKO
# ============================================

def route_to_mcp(task: str) -> Optional[Tuple[str, str, Dict]]:
    """
    Analyze a task and determine if it should be routed to an MCP.

    Returns (mcp_name, method, params) or None.
    """
    task_lower = task.lower()

    # GitHub operations
    if "github" in task_lower or "issue" in task_lower or "pr" in task_lower:
        for name in _mcp_servers:
            if "github" in name.lower():
                return (name, "auto", {"task": task})

    # Web search
    if "search" in task_lower or "look up" in task_lower:
        for name in _mcp_servers:
            if "brave" in name.lower() or "search" in name.lower():
                return (name, "brave_web_search", {"query": task})

    # Database operations
    if "database" in task_lower or "sql" in task_lower:
        for name in _mcp_servers:
            if "postgres" in name.lower() or "sqlite" in name.lower():
                return (name, "auto", {"task": task})

    return None


def format_mcp_list() -> str:
    """Format available MCPs for display."""
    mcps = get_available_mcps()

    if not mcps:
        return "No MCP servers configured in Claude Desktop."

    msg = "**Available MCP Servers:**\n\n"
    for mcp in mcps:
        msg += f"• **{mcp['name']}**: {mcp['description']}\n"

    return msg


# Initialize on import
load_mcp_config()
