"""
Kiyomi — Model Router
Routes messages to the right AI provider (Gemini, Claude, GPT).
User never sees this — it just works.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def classify_message(text: str) -> str:
    """Classify what kind of task this is.

    Returns: 'chat' (fast, Sonnet) or 'task' (serious, Opus)
    """
    text_lower = text.lower()

    # Explicit model triggers (user override)
    if any(t in text_lower for t in ['/opus', 'use opus', 'deep mode', 'full power']):
        return 'task'
    if any(t in text_lower for t in ['/sonnet', 'use sonnet', 'quick mode']):
        return 'chat'

    # Building / coding -> always task (Opus)
    building_words = [
        'build me', 'build a ', 'create app', 'create an app',
        'create a script', 'create a program', 'create a bot',
        'create a website', 'create a site', 'create a tool',
        'create a database', 'create a schema', 'create a pipeline',
        'create a function', 'create a class', 'create a component',
        'create a api', 'create a server', 'create a service',
        'python script', 'bash script', 'shell script',
        'make a website', 'make me a website', 'make me a ',
        'write code', 'write a script', 'implement',
        'deploy', 'set up a server', 'configure',
        'code a ', 'code an ', 'code me',
        'automate this', 'automation script',
    ]

    # Serious analysis / work -> task (Opus)
    task_words = [
        'write me', 'write a ', 'draft', 'compose', 'essay',
        'business plan', 'marketing plan', 'strategy',
        'proposal', 'analyze', 'analysis', 'explain in detail',
        'research', 'generate report', 'outline',
        'resume', 'cover letter', 'help me write',
        'create a plan', 'create a report',
        'create a document', 'create a draft',
        'trade', 'trading', 'portfolio', 'investment',
        'buy ', 'sell ', 'position', 'market analysis',
        'compare', 'evaluate', 'break down', 'deep dive',
        'summarize', 'explain this', 'explain how', 'explain why',
        'debug', 'fix this', 'troubleshoot', 'diagnose',
        'refactor', 'optimize', 'review code', 'audit',
        'send email', 'compose email', 'write email',
        'scan', 'monitor', 'check my', 'pull up',
    ]

    if any(kw in text_lower for kw in building_words):
        return 'task'
    if any(kw in text_lower for kw in task_words):
        return 'task'

    # Short messages -> chat (greetings, acks, quick questions)
    if len(text.split()) < 8:
        return 'chat'

    # Default: chat (Sonnet handles most things fine, safe default)
    return 'chat'


def pick_model(task_type: str, config: dict) -> tuple[str, str]:
    """Pick the best model for this task.

    Returns: (provider, model_name)

    For claude-cli: task_type 'task' -> Opus, 'chat' -> Sonnet.
    Trusts the user's configured provider — CLI availability is checked downstream.
    """
    provider = config.get("provider", "gemini")

    # CLI provider — trust the config, CLIRouter handles availability + fallback
    if provider.endswith("-cli"):
        if provider == "claude-cli":
            if task_type == "task":
                model = config.get("task_model") or "claude-opus-4-6"
            else:
                model = config.get("chat_model") or "claude-sonnet-4-5-20250929"
            return (provider, model)
        cli_name = provider.replace("-cli", "")
        return (provider, cli_name)

    # API provider — use configured model or defaults
    from engine.config import get_model
    api_key_map = {"gemini": "gemini_key", "anthropic": "anthropic_key", "openai": "openai_key"}
    if provider in api_key_map and config.get(api_key_map[provider]):
        return (provider, get_model(config))

    # Fallback: try to find any available CLI
    from engine.config import detect_available_clis
    available_clis = detect_available_clis()
    for cli in ["claude-cli", "gemini-cli", "codex-cli"]:
        if cli in available_clis:
            cli_name = cli.replace("-cli", "")
            return (cli, cli_name)

    # API fallback
    if config.get("anthropic_key"):
        return ('anthropic', 'claude-sonnet-4-20250514')
    if config.get("gemini_key"):
        return ('gemini', 'gemini-2.0-flash')
    if config.get("openai_key"):
        return ('openai', 'gpt-4o')

    # Last resort
    return (provider, get_model(config))
