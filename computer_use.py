"""
Kiyomi Computer Use - Browser and Desktop Control

Uses Anthropic's computer use API to control the Mac Mini.
Kiyomi can browse the web, fill forms, send emails, and run workflows.
"""
import asyncio
import base64
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

import anthropic
import pyautogui
from PIL import Image

from config import BASE_DIR, TIMEZONE
import pytz

logger = logging.getLogger(__name__)

# Computer use configuration
SCREENSHOT_DIR = BASE_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

# Screen dimensions - will be detected automatically
SCREEN_WIDTH = None
SCREEN_HEIGHT = None

# Safety settings for pyautogui
pyautogui.FAILSAFE = True  # Move mouse to corner to abort
pyautogui.PAUSE = 0.5  # Pause between actions


def get_screen_size() -> Tuple[int, int]:
    """Get the screen dimensions."""
    global SCREEN_WIDTH, SCREEN_HEIGHT
    if SCREEN_WIDTH is None or SCREEN_HEIGHT is None:
        SCREEN_WIDTH, SCREEN_HEIGHT = pyautogui.size()
    return SCREEN_WIDTH, SCREEN_HEIGHT


def take_screenshot() -> Tuple[str, str]:
    """
    Take a screenshot and return (base64_data, file_path).
    """
    tz = pytz.timezone(TIMEZONE)
    timestamp = datetime.now(tz).strftime("%Y%m%d_%H%M%S")
    filepath = SCREENSHOT_DIR / f"screen_{timestamp}.png"

    # Take screenshot using pyautogui
    screenshot = pyautogui.screenshot()
    screenshot.save(filepath)

    # Convert to base64
    with open(filepath, "rb") as f:
        base64_data = base64.standard_b64encode(f.read()).decode("utf-8")

    logger.info(f"Screenshot saved: {filepath}")
    return base64_data, str(filepath)


def execute_computer_action(action: Dict[str, Any]) -> str:
    """
    Execute a computer use action returned by Claude.

    Actions can be:
    - screenshot: Take a screenshot
    - click: Click at x, y coordinates
    - type: Type text
    - key: Press a key or key combination
    - scroll: Scroll up or down
    - cursor_position: Get current cursor position
    """
    action_type = action.get("action")

    try:
        if action_type == "screenshot":
            base64_data, filepath = take_screenshot()
            return f"Screenshot taken: {filepath}"

        elif action_type == "click":
            x = action.get("coordinate", [0, 0])[0]
            y = action.get("coordinate", [0, 0])[1]
            button = action.get("button", "left")  # left, right, middle

            # Move and click
            pyautogui.click(x, y, button=button)
            logger.info(f"Clicked at ({x}, {y}) with {button} button")
            return f"Clicked at ({x}, {y})"

        elif action_type == "double_click":
            x = action.get("coordinate", [0, 0])[0]
            y = action.get("coordinate", [0, 0])[1]

            pyautogui.doubleClick(x, y)
            logger.info(f"Double-clicked at ({x}, {y})")
            return f"Double-clicked at ({x}, {y})"

        elif action_type == "type":
            text = action.get("text", "")

            # Type the text
            pyautogui.typewrite(text, interval=0.02)
            logger.info(f"Typed: {text[:50]}...")
            return f"Typed text ({len(text)} chars)"

        elif action_type == "key":
            key = action.get("key", "")

            # Handle special key combinations
            if "+" in key:
                # Key combination like "command+c"
                keys = key.lower().split("+")
                pyautogui.hotkey(*keys)
            else:
                pyautogui.press(key.lower())

            logger.info(f"Pressed key: {key}")
            return f"Pressed {key}"

        elif action_type == "scroll":
            x = action.get("coordinate", [None, None])[0]
            y = action.get("coordinate", [None, None])[1]
            direction = action.get("direction", "down")
            amount = action.get("amount", 3)

            # Move to position if specified
            if x is not None and y is not None:
                pyautogui.moveTo(x, y)

            # Scroll (positive = up, negative = down)
            clicks = amount if direction == "up" else -amount
            pyautogui.scroll(clicks)

            logger.info(f"Scrolled {direction} by {amount}")
            return f"Scrolled {direction}"

        elif action_type == "cursor_position":
            x, y = pyautogui.position()
            return f"Cursor at ({x}, {y})"

        elif action_type == "move":
            x = action.get("coordinate", [0, 0])[0]
            y = action.get("coordinate", [0, 0])[1]

            pyautogui.moveTo(x, y)
            logger.info(f"Moved cursor to ({x}, {y})")
            return f"Moved to ({x}, {y})"

        elif action_type == "drag":
            start_x = action.get("start_coordinate", [0, 0])[0]
            start_y = action.get("start_coordinate", [0, 0])[1]
            end_x = action.get("coordinate", [0, 0])[0]
            end_y = action.get("coordinate", [0, 0])[1]

            pyautogui.moveTo(start_x, start_y)
            pyautogui.drag(end_x - start_x, end_y - start_y)
            logger.info(f"Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})")
            return f"Dragged to ({end_x}, {end_y})"

        else:
            logger.warning(f"Unknown action type: {action_type}")
            return f"Unknown action: {action_type}"

    except Exception as e:
        logger.error(f"Action failed: {e}")
        return f"Action failed: {e}"


async def run_computer_task(
    task: str,
    send_callback=None,
    max_steps: int = 50
) -> Tuple[bool, str]:
    """
    Run a computer use task with Claude.

    Args:
        task: Description of what to do (e.g., "Open Safari and search for weather")
        send_callback: Optional callback to send progress updates
        max_steps: Maximum number of action steps before stopping

    Returns:
        (success, result_message)
    """
    client = anthropic.Anthropic()

    # Get screen dimensions
    width, height = get_screen_size()

    # Define the computer tool
    tools = [
        {
            "type": "computer_20241022",
            "name": "computer",
            "display_width_px": width,
            "display_height_px": height,
            "display_number": 1,
        }
    ]

    # Initial message with the task
    messages = [
        {
            "role": "user",
            "content": f"""Please help me with this task on my Mac:

{task}

Start by taking a screenshot to see the current state of the screen."""
        }
    ]

    if send_callback:
        await send_callback(f"🖥️ Starting computer task: {task[:100]}...")

    steps_taken = 0
    last_update = ""

    try:
        while steps_taken < max_steps:
            steps_taken += 1

            # Call Claude with computer use
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                tools=tools,
                messages=messages,
                system="You are helping control a Mac computer. Be efficient and precise with your actions. When you've completed the task or cannot proceed, say so clearly."
            )

            # Check if we're done
            if response.stop_reason == "end_turn":
                # Extract final text response
                final_text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        final_text = block.text
                        break

                if send_callback:
                    await send_callback(f"✅ Task complete!\n\n{final_text[:500]}")

                return True, final_text

            # Process tool uses
            assistant_content = response.content
            tool_results = []

            for block in assistant_content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    tool_use_id = block.id

                    if tool_name == "computer":
                        action_type = tool_input.get("action", "unknown")

                        # Execute the action
                        if action_type == "screenshot":
                            base64_data, filepath = take_screenshot()

                            # Send screenshot result
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "content": [
                                    {
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": "image/png",
                                            "data": base64_data
                                        }
                                    }
                                ]
                            })

                            update_msg = "📸 Screenshot taken"
                        else:
                            # Execute other actions
                            result = execute_computer_action(tool_input)

                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "content": result
                            })

                            update_msg = f"🖱️ {result}"

                        # Send progress update (not too frequently)
                        if send_callback and update_msg != last_update:
                            if steps_taken % 3 == 0 or "complete" in update_msg.lower():
                                await send_callback(f"Step {steps_taken}: {update_msg}")
                            last_update = update_msg

                        # Small delay between actions for stability
                        await asyncio.sleep(0.5)

            # Add assistant response and tool results to messages
            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})

        # Max steps reached
        if send_callback:
            await send_callback(f"⚠️ Task stopped after {max_steps} steps. May be incomplete.")

        return False, f"Task stopped after {max_steps} steps"

    except Exception as e:
        logger.error(f"Computer task failed: {e}")
        if send_callback:
            await send_callback(f"❌ Computer task failed: {e}")
        return False, str(e)


async def open_application(app_name: str) -> Tuple[bool, str]:
    """Open a macOS application."""
    try:
        subprocess.run(["open", "-a", app_name], check=True)
        await asyncio.sleep(1)  # Wait for app to open
        return True, f"Opened {app_name}"
    except Exception as e:
        return False, f"Failed to open {app_name}: {e}"


async def open_url(url: str) -> Tuple[bool, str]:
    """Open a URL in the default browser."""
    try:
        subprocess.run(["open", url], check=True)
        await asyncio.sleep(2)  # Wait for page to load
        return True, f"Opened {url}"
    except Exception as e:
        return False, f"Failed to open {url}: {e}"


# Pre-built workflows
async def send_email_workflow(
    to: str,
    subject: str,
    body: str,
    send_callback=None
) -> Tuple[bool, str]:
    """
    Send an email using the Mail app or Gmail.
    """
    task = f"""Send an email with these details:

To: {to}
Subject: {subject}
Body:
{body}

Please:
1. Open the Mail app (or Safari to Gmail if Mail isn't set up)
2. Compose a new email
3. Fill in the recipient, subject, and body
4. Send the email
5. Confirm it was sent"""

    return await run_computer_task(task, send_callback)


async def web_research_workflow(
    query: str,
    send_callback=None
) -> Tuple[bool, str]:
    """
    Research a topic on the web and summarize findings.
    """
    task = f"""Research this topic and summarize what you find:

Query: {query}

Please:
1. Open Safari
2. Search for the query on Google
3. Visit 2-3 relevant results
4. Summarize the key information you find"""

    return await run_computer_task(task, send_callback)


def get_recent_screenshots(limit: int = 5) -> List[Path]:
    """Get the most recent screenshots."""
    screenshots = sorted(SCREENSHOT_DIR.glob("screen_*.png"), reverse=True)
    return screenshots[:limit]


def cleanup_old_screenshots(keep_count: int = 20):
    """Remove old screenshots, keeping only the most recent ones."""
    screenshots = sorted(SCREENSHOT_DIR.glob("screen_*.png"), reverse=True)
    for old_screenshot in screenshots[keep_count:]:
        old_screenshot.unlink()
        logger.info(f"Deleted old screenshot: {old_screenshot}")
