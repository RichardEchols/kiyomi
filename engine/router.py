"""
Kiyomi Lite — Model Router
Routes messages to the right AI provider (Gemini, Claude, GPT).
User never sees this — it just works.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def classify_message(text: str) -> str:
    """Classify what kind of task this is.
    
    Returns: 'simple', 'writing', 'building'
    """
    text_lower = text.lower()
    
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
    writing_words = [
        'write me', 'write a ', 'draft', 'compose', 'essay',
        'business plan', 'marketing', 'strategy', 'proposal',
        'analyze', 'analysis', 'explain in detail', 'research',
        'generate report', 'summarize', 'summary', 'outline',
        'resume', 'cover letter', 'help me write',
        'create a plan', 'create a summary', 'create a report',
        'create a list', 'create a document', 'create a draft',
    ]
    simple_words = [
        'good morning', 'hello', 'hi', 'hey', 'what time',
        'remind me', 'schedule', 'weather', 'remember',
        'how are you', 'thank', 'good night', 'good evening',
        'what can you do', 'tell me about',
    ]
    
    if any(kw in text_lower for kw in building_words):
        return 'building'
    if any(kw in text_lower for kw in writing_words):
        return 'writing'
    if any(kw in text_lower for kw in simple_words):
        return 'simple'
    if len(text.split()) < 8:
        return 'simple'
    return 'writing'


def pick_model(task_type: str, config: dict) -> tuple[str, str]:
    """Pick the best model for this task.

    Returns: (provider, model_name)

    Always respects the user's configured provider first.
    Only falls back to other providers if the chosen one isn't available.
    """
    provider = config.get("provider", "gemini")

    # Check for CLI providers
    from engine.config import detect_available_clis, get_model
    available_clis = detect_available_clis()

    # If user chose a CLI provider and it's available, use it
    if provider in available_clis:
        cli_name = provider.replace("-cli", "")
        return (provider, cli_name)

    # If user chose an API provider with a key, use it
    api_key_map = {"gemini": "gemini_key", "anthropic": "anthropic_key", "openai": "openai_key"}
    if provider in api_key_map and config.get(api_key_map[provider]):
        return (provider, get_model(config))

    # User's chosen provider not available — fall back intelligently
    # CLI fallback order depends on task type
    if task_type == 'building':
        cli_order = ["claude-cli", "gemini-cli", "codex-cli"]
    else:
        cli_order = ["claude-cli", "gemini-cli", "codex-cli"]

    for cli in cli_order:
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
