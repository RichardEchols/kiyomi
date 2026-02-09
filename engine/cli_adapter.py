"""
Kiyomi v5.0 — CLI Adapter Layer
Thin adapters for calling Claude CLI, Codex CLI, and Gemini CLI.
Each adapter knows how to build commands and parse responses.
"""
import json
import logging
import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

logger = logging.getLogger("kiyomi.cli_adapter")

# Identity file names per CLI
IDENTITY_FILES = {
    "claude": "CLAUDE.md",
    "codex": "AGENTS.md",
    "gemini": "GEMINI.md",
}


def _expanded_path() -> str:
    """Get PATH with common install locations for launchd compatibility."""
    extra = [
        "/opt/homebrew/bin",
        "/usr/local/bin",
        str(Path.home() / ".local" / "bin"),
        str(Path.home() / ".npm-global" / "bin"),
    ]
    path = os.environ.get("PATH", "")
    for p in extra:
        if p not in path:
            path = f"{p}:{path}"
    return path


def _which(name: str) -> Optional[str]:
    """Find a CLI binary on expanded PATH."""
    return shutil.which(name, path=_expanded_path())


def get_env() -> dict:
    """Build environment dict for subprocess calls."""
    env = os.environ.copy()
    env["PATH"] = _expanded_path()
    # Disable interactive prompts
    env["CI"] = "1"
    return env


class CLIAdapter(ABC):
    """Base adapter for calling an AI CLI."""

    name: str = ""
    identity_file: str = ""

    @abstractmethod
    def build_command(
        self,
        message: str,
        session_id: Optional[str] = None,
        model: Optional[str] = None,
        cwd: Optional[str] = None,
        image_path: Optional[str] = None,
    ) -> list[str]:
        """Build the CLI command as a list of args."""
        ...

    @abstractmethod
    def parse_response(self, stdout: str, stderr: str, returncode: int) -> tuple[str, Optional[str]]:
        """Parse CLI output into (response_text, session_id)."""
        ...

    def get_binary(self) -> Optional[str]:
        """Find the CLI binary."""
        return _which(self.name)


class ClaudeAdapter(CLIAdapter):
    """Adapter for Claude CLI (claude -p)."""

    name = "claude"
    identity_file = "CLAUDE.md"

    def build_command(self, message, session_id=None, model=None, cwd=None, image_path=None):
        binary = self.get_binary()
        if not binary:
            raise FileNotFoundError("Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code")

        cmd = [binary, "-p", message, "--output-format", "json", "--dangerously-skip-permissions"]

        if session_id:
            cmd.extend(["--resume", session_id])
        if model:
            cmd.extend(["--model", model])

        return cmd

    def parse_response(self, stdout, stderr, returncode):
        if returncode != 0 and not stdout.strip():
            error = stderr.strip() if stderr else f"Claude CLI exited with code {returncode}"
            return f"Error: {error}", None

        # Claude outputs JSON with result and session_id
        try:
            data = json.loads(stdout)
            text = data.get("result", "")
            sid = data.get("session_id")
            return text, sid
        except json.JSONDecodeError:
            # Fallback: return raw stdout
            return stdout.strip(), None


class CodexAdapter(CLIAdapter):
    """Adapter for Codex CLI (codex exec)."""

    name = "codex"
    identity_file = "AGENTS.md"

    def build_command(self, message, session_id=None, model=None, cwd=None, image_path=None):
        binary = self.get_binary()
        if not binary:
            raise FileNotFoundError("Codex CLI not found. Install with: npm install -g @openai/codex")

        if session_id:
            cmd = [binary, "exec", "resume", session_id, message]
        else:
            cmd = [binary, "exec", message]

        cmd.extend(["--json", "--dangerously-bypass-approvals-and-sandbox", "--skip-git-repo-check"])

        if model:
            cmd.extend(["-m", model])
        if image_path:
            cmd.extend(["-i", image_path])

        return cmd

    def parse_response(self, stdout, stderr, returncode):
        if returncode != 0 and not stdout.strip():
            error = stderr.strip() if stderr else f"Codex CLI exited with code {returncode}"
            return f"Error: {error}", None

        # Codex outputs JSONL — find last agent_message and thread_id
        text = ""
        session_id = None

        for line in stdout.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Look for thread ID
            event_type = data.get("type", "")
            if event_type == "thread.started":
                session_id = data.get("thread_id")

            # Look for the last agent message
            if event_type == "item.completed":
                item = data.get("item", {})
                if item.get("type") == "agent_message":
                    # Extract text from content array
                    for block in item.get("content", []):
                        if block.get("type") == "output_text":
                            text = block.get("text", "")

        if not text:
            # Fallback: return raw stdout
            text = stdout.strip()

        return text, session_id


class GeminiAdapter(CLIAdapter):
    """Adapter for Gemini CLI (gemini -p)."""

    name = "gemini"
    identity_file = "GEMINI.md"

    def build_command(self, message, session_id=None, model=None, cwd=None, image_path=None):
        binary = self.get_binary()
        if not binary:
            raise FileNotFoundError("Gemini CLI not found. Install with: npm install -g @anthropic-ai/gemini-cli")

        cmd = [binary, "-p", message, "-o", "json", "-y"]

        if session_id:
            cmd.extend(["--resume", session_id])
        if model:
            cmd.extend(["-m", model])

        return cmd

    def parse_response(self, stdout, stderr, returncode):
        if returncode != 0 and not stdout.strip():
            error = stderr.strip() if stderr else f"Gemini CLI exited with code {returncode}"
            return f"Error: {error}", None

        try:
            data = json.loads(stdout)
            text = data.get("response", "")
            sid = data.get("session_id")
            return text, sid
        except json.JSONDecodeError:
            return stdout.strip(), None


# Registry
_ADAPTERS = {
    "claude": ClaudeAdapter,
    "codex": CodexAdapter,
    "gemini": GeminiAdapter,
}


def get_adapter(cli_name: str) -> CLIAdapter:
    """Get the adapter for a given CLI name."""
    cls = _ADAPTERS.get(cli_name)
    if not cls:
        raise ValueError(f"Unknown CLI: {cli_name}. Available: {list(_ADAPTERS.keys())}")
    return cls()


def detect_available_clis() -> dict[str, str]:
    """Detect which AI CLIs are installed. Returns {name: path}."""
    available = {}
    for name in _ADAPTERS:
        path = _which(name)
        if path:
            available[name] = path
    return available


def sync_identity_file(cli_name: str, workspace: Path):
    """Copy identity.md to the CLI-specific filename in workspace.

    Source of truth is always ~/.kiyomi/identity.md.
    This copies it to CLAUDE.md, AGENTS.md, or GEMINI.md as needed.
    """
    source = workspace / "identity.md"
    if not source.exists():
        return

    target_name = IDENTITY_FILES.get(cli_name)
    if not target_name:
        return

    target = workspace / target_name
    # Always overwrite — identity.md is source of truth
    import shutil as _shutil
    _shutil.copy2(str(source), str(target))
    logger.debug(f"Synced identity.md → {target_name}")
