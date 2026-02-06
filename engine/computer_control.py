"""
Kiyomi Computer Control — Bridge between Kiyomi and Agent TARS
Detects computer control requests and executes them via Agent TARS CLI.
"""
import asyncio
import logging
import re
import shutil
from typing import Optional

logger = logging.getLogger(__name__)

# Computer action detection — EXPLICIT phrases only.
# Previous patterns were too aggressive (e.g. "open\s+\w+" matched normal conversation).
# Now we only trigger on unambiguous computer-control language.
COMPUTER_ACTION_PATTERNS = [
    # Explicit "my computer" phrases
    r"on\s+my\s+(computer|mac|laptop|desktop)[,\s]",
    r"use\s+my\s+(computer|mac|laptop|desktop)\s+to",
    r"control\s+my\s+(computer|mac|laptop|desktop)",

    # Explicit screenshot request
    r"take\s+a\s+screenshot",
    r"show\s+me\s+(what'?s\s+on\s+)?(my\s+)?screen",

    # Explicit app control with known app names
    r"(open|launch|switch\s+to)\s+(safari|chrome|firefox|terminal|finder|notes|mail|calendar|slack|discord|spotify|vscode|xcode)",

    # Explicit click/type on screen
    r"click\s+(on\s+)?(the\s+)?button",
    r"click\s+(on\s+)?(the\s+)?link",
    r"type\s+into\s+(the\s+)?(search|field|box|input)",
    r"fill\s+out\s+(the\s+)?form",
]


def is_computer_action(message: str) -> bool:
    """
    Detect if a user message is requesting computer control.

    Only triggers on EXPLICIT computer-control language to avoid
    false positives on normal conversation.

    Args:
        message: User message to analyze

    Returns:
        bool: True if this appears to be a computer control request
    """
    if not message or not message.strip():
        return False

    message_lower = message.lower().strip()

    # Check for explicit computer action patterns
    for pattern in COMPUTER_ACTION_PATTERNS:
        if re.search(pattern, message_lower):
            logger.info(f"Computer action detected: pattern '{pattern}' matched '{message[:100]}...'")
            return True

    return False


async def execute_computer_action(
    message: str, 
    provider: str = "anthropic", 
    api_key: str = "", 
    model: Optional[str] = None,
    timeout: int = 120
) -> str:
    """
    Execute a computer control action using Agent TARS.
    
    Args:
        message: User's computer control request
        provider: AI provider (anthropic, openai, volcengine)
        api_key: API key for the provider
        model: Optional model name
        timeout: Timeout in seconds (default 120)
        
    Returns:
        str: Result of the computer action or error message
    """
    if not message or not message.strip():
        return "No computer action specified."
    
    # Check if agent-tars CLI is available
    if not shutil.which("agent-tars"):
        return (
            "Agent TARS CLI is not installed. I can install it for you!\n\n"
            "Agent TARS is ByteDance's open-source AI agent that can see your screen "
            "and control your computer. It requires Node.js >= 22.\n\n"
            "Would you like me to install it? Just say 'install agent-tars'."
        )
    
    if not api_key:
        return (
            f"I need an API key for {provider} to control your computer.\n\n"
            f"Please provide your {provider} API key in Kiyomi settings."
        )
    
    # Safety confirmation message
    safety_message = (
        f"🤖 I'm about to control your computer to: {message}\n\n"
        f"This action will be performed by Agent TARS (ByteDance's AI agent) "
        f"using {provider}. This may take 30-120 seconds.\n\n"
        f"Starting computer control..."
    )
    
    logger.info(f"Executing computer action via Agent TARS: {message[:100]}...")
    
    try:
        # Build the agent-tars command
        cmd = ["agent-tars", "--provider", provider, "--apiKey", api_key]
        
        if model:
            cmd.extend(["--model", model])
        
        # Add the user's request
        cmd.append(message)
        
        logger.info(f"Agent TARS command: {' '.join(cmd[:4])} [key hidden] {cmd[5:]}")
        
        # Execute with timeout
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return (
                f"⏰ Computer action timed out after {timeout} seconds.\n\n"
                f"The action '{message[:100]}...' took too long to complete. "
                f"This can happen with complex tasks or if the AI needs more time to understand the screen."
            )
        
        # Parse results
        if proc.returncode == 0:
            output = stdout.decode('utf-8', errors='replace').strip()
            
            if output:
                return (
                    f"✅ Computer action completed!\n\n"
                    f"**Action:** {message}\n\n"
                    f"**Result:**\n{output[:500]}" +
                    ("..." if len(output) > 500 else "")
                )
            else:
                return (
                    f"✅ Computer action completed!\n\n"
                    f"**Action:** {message}\n\n"
                    f"The action was performed successfully."
                )
        else:
            error_output = stderr.decode('utf-8', errors='replace').strip()
            
            # Common error patterns and user-friendly messages
            if "api key" in error_output.lower() or "unauthorized" in error_output.lower():
                return (
                    f"❌ Authentication failed with {provider}.\n\n"
                    f"Please check your API key in Kiyomi settings and make sure it's valid."
                )
            elif "not found" in error_output.lower() or "no such file" in error_output.lower():
                return (
                    f"❌ Couldn't find the application or element you requested.\n\n"
                    f"**Action:** {message}\n\n"
                    f"Try being more specific about what you want to control, or make sure "
                    f"the application is open and visible on your screen."
                )
            elif "timeout" in error_output.lower():
                return (
                    f"⏰ Agent TARS couldn't complete the action in time.\n\n"
                    f"**Action:** {message}\n\n"
                    f"This might be because the task is complex or the screen changed. "
                    f"Try breaking it into smaller steps."
                )
            else:
                return (
                    f"❌ Computer action failed.\n\n"
                    f"**Action:** {message}\n\n"
                    f"**Error:** {error_output[:300]}" +
                    ("..." if len(error_output) > 300 else "") +
                    f"\n\nTry rephrasing your request or making it more specific."
                )
    
    except Exception as e:
        logger.error(f"Computer control error: {e}")
        return (
            f"❌ Computer control error: {str(e)[:200]}...\n\n"
            f"Please try again or contact support if the problem persists."
        )


def get_computer_control_status() -> dict:
    """
    Get the current status of computer control capabilities.
    
    Returns:
        dict: Status information including Agent TARS availability
    """
    agent_tars_path = shutil.which("agent-tars")
    
    return {
        "agent_tars_installed": bool(agent_tars_path),
        "agent_tars_path": agent_tars_path,
        "supported_providers": ["anthropic", "openai", "volcengine"],
        "node_available": bool(shutil.which("node")),
        "npm_available": bool(shutil.which("npm"))
    }


# For testing
if __name__ == "__main__":
    # Test the detection function
    test_cases = [
        ("open Safari and go to google.com", True),
        ("what is the weather today", False),
        ("click on the submit button", True),
        ("remember that meeting is at 3pm", False),
        ("book a flight to New York", True),
        ("how do I cook pasta", False),
        ("take a screenshot of my desktop", True),
        ("what time is it", False),
        ("on my computer, open the settings app", True),
        ("tell me about machine learning", False),
    ]
    
    print("Testing computer action detection:")
    for message, expected in test_cases:
        result = is_computer_action(message)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{message}' -> {result} (expected {expected})")