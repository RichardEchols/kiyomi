#!/usr/bin/env python3
"""
Kiyomi - Richard's Personal 24/7 AI Assistant
Main Telegram Bot
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
import pytz

from telegram import Update, Bot
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters, CallbackQueryHandler
)
from telegram.constants import ParseMode, ChatAction

from config import (
    TELEGRAM_BOT_TOKEN, ALLOWED_USER_IDS, TIMEZONE,
    BOT_NAME, BOT_EMOJI, BASE_DIR, LOGS_DIR
)
from supervisor import Supervisor
from security import (
    is_authorized, contains_blocked_pattern,
    needs_confirmation, sanitize_for_logging
)
from executor import (
    execute_claude, execute_shell, save_conversation_summary,
    get_conversation_history, clear_conversation_history,
    cancel_current_task, get_current_task,
    spawn_subagent, get_subagent_status, list_running_subagents, cancel_subagent
)
from memory_manager import (
    load_session_context, log_command, log_to_today,
    read_heartbeat, get_today_date
)
from heartbeat import (
    start_heartbeat_scheduler, update_last_message_time,
    run_heartbeat
)
from learning import start_learning_loop, force_learning_cycle, get_learning_status
from reminders import (
    start_reminder_scheduler, add_reminder, remove_reminder,
    list_reminders, parse_reminder_time
)
from proactive import (
    update_last_richard_message, parse_natural_command,
    execute_natural_command, is_session_idle, do_session_summary,
    enable_factory_mode, is_factory_mode, do_silent_prep, is_prep_time
)
from skills import inject_skill_context, list_available_skills, load_skill
from web_tools import web_search, web_fetch, get_weather, get_daily_text
from projects import (
    detect_project_from_text, get_project_by_name, list_projects,
    parse_quick_command, get_project_context, Project
)
from session_state import (
    set_current_project, get_current_project_name, set_last_error,
    add_context_note, get_state
)
from deploy_tools import smart_deploy, get_vercel_logs, rollback_vercel
from git_tools import git_status, commit_fix, git_log
from monitoring import start_monitoring_loop, run_monitoring_check, generate_status_report, quick_check
from voice import quick_speak, cleanup_voice_file
from swarm import should_spawn_swarm, spawn_swarm, get_active_swarms, get_swarm_status
from self_update import (
    process_self_update_request, restart_keiko, get_update_history,
    list_kiyomi_files, get_recent_backups
)
from escalation import get_escalation_stats, get_recent_escalations
from corrections import get_all_preferences, get_correction_stats
from cost_tracking import (
    generate_cost_report, get_daily_cost, set_daily_budget,
    get_alert_settings
)
from streaming import StreamingProgress, parse_claude_output_for_progress
from session_manager import (
    get_current_session, get_session_summary, is_continue_command,
    get_continue_prompt, should_continue, end_session
)
from smart_response import analyze_task, get_confidence_prefix, should_ask_clarification
from quick_actions import (
    handle_callback_query, build_continue_keyboard, build_quick_actions_keyboard,
    suggest_actions_for_message
)
from file_handler import process_file, build_file_prompt, handle_file_upload
from mcp_bridge import get_available_mcps, format_mcp_list
from plugin_system import (
    initialize_plugin_system, load_all_plugins, get_loaded_plugins,
    format_plugin_list, dispatch_message, dispatch_command, dispatch_trigger,
    reload_plugin, unload_plugin
)
from skill_loader import format_skill_list, get_skill_context_for_task, list_skills
from watchdog import start_health_monitor, record_activity, get_health_status, get_uptime, report_crash
from connection_manager import safe_send, get_connection_status
from computer_use import (
    run_computer_task, send_email_workflow, web_research_workflow,
    open_application, open_url, get_recent_screenshots, cleanup_old_screenshots
)

# ============================================
# LOGGING SETUP
# ============================================
LOGS_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOGS_DIR / "bot.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# STATE
# ============================================
pending_confirmations: Dict[int, str] = {}
current_task: Dict = {}
bot_start_time: datetime = None
last_kiyomi_response: Optional[str] = None  # Track for correction detection
task_supervisor = Supervisor()  # Manages all background tasks with auto-restart

# Command history persistence
COMMAND_HISTORY_FILE = BASE_DIR / "command_history.json"

def _load_command_history() -> List[Dict]:
    """Load command history from file."""
    try:
        if COMMAND_HISTORY_FILE.exists():
            import json
            with open(COMMAND_HISTORY_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return []

def _save_command_history(history: List[Dict]) -> None:
    """Save command history to file."""
    try:
        import json
        # Keep last 100 commands
        history = history[-100:]
        with open(COMMAND_HISTORY_FILE, "w") as f:
            json.dump(history, f)
    except Exception:
        pass

command_history: List[Dict] = _load_command_history()

# Telegram message limit
MAX_MESSAGE_LENGTH = 4096


# ============================================
# HELPER FUNCTIONS
# ============================================

async def send_long_message(update: Update, text: str) -> None:
    """Send a message, splitting if needed for Telegram's limit."""
    if len(text) <= MAX_MESSAGE_LENGTH:
        await update.message.reply_text(text)
        return

    # Split into chunks
    chunks = []
    while text:
        if len(text) <= MAX_MESSAGE_LENGTH:
            chunks.append(text)
            break

        # Find a good split point
        split_at = text.rfind('\n', 0, MAX_MESSAGE_LENGTH)
        if split_at == -1:
            split_at = text.rfind(' ', 0, MAX_MESSAGE_LENGTH)
        if split_at == -1:
            split_at = MAX_MESSAGE_LENGTH

        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()

    for i, chunk in enumerate(chunks):
        if i > 0:
            await asyncio.sleep(0.5)  # Rate limiting
        await update.message.reply_text(chunk)


async def send_to_richard(bot: Bot, text: str) -> None:
    """Send a message to Richard."""
    for user_id in ALLOWED_USER_IDS:
        try:
            if len(text) <= MAX_MESSAGE_LENGTH:
                await bot.send_message(chat_id=user_id, text=text)
            else:
                # Split long messages
                chunks = [text[i:i+MAX_MESSAGE_LENGTH] for i in range(0, len(text), MAX_MESSAGE_LENGTH)]
                for chunk in chunks:
                    await bot.send_message(chat_id=user_id, text=chunk)
                    await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Error sending to Richard: {e}")


# ============================================
# COMMAND HANDLERS
# ============================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    if not is_authorized(update.effective_user.id):
        return

    await update.message.reply_text(
        f"{BOT_EMOJI} Hey Richard! {BOT_NAME} is ready.\n\n"
        f"Just send me any task and I'll handle it via Claude Code.\n\n"
        f"Commands:\n"
        f"/status - Bot status\n"
        f"/history - Recent commands\n"
        f"/heartbeat - Force heartbeat check\n"
        f"/memory - Today's memory\n"
        f"/cancel - Cancel current task\n"
        f"/help - This message"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    if not is_authorized(update.effective_user.id):
        return

    await update.message.reply_text(
        f"{BOT_EMOJI} **{BOT_NAME} Commands**\n\n"
        f"**Computer Use:**\n"
        f"/computer <task> - Control the Mac\n"
        f"/browse <url/search> - Browse web\n"
        f"/email <to|subj|body> - Send email\n"
        f"/screenshot - Take screenshot\n"
        f"/openapp <name> - Open an app\n\n"
        f"**Projects:**\n"
        f"/projects - List all projects\n"
        f"/deploy <name> - Deploy a project\n"
        f"/check [name] - Check if site is up\n"
        f"/logs <name> - Get Vercel logs\n\n"
        f"**Swarm & Agents:**\n"
        f"/swarm <task> - Spawn agent swarm\n"
        f"/spawn <id> <task> - Spawn agent\n"
        f"/agents - List agents\n\n"
        f"**Memory & Status:**\n"
        f"/memory - Today's memory\n"
        f"/status - Bot status\n"
        f"/health - System health\n"
        f"/costs - API cost report\n\n"
        f"Send any message to execute via Claude!",
        parse_mode=ParseMode.MARKDOWN
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command."""
    if not is_authorized(update.effective_user.id):
        return

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    uptime = "Unknown"
    if bot_start_time:
        delta = now - bot_start_time
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime = f"{hours}h {minutes}m {seconds}s"

    task_status = "None" if not current_task else current_task.get("description", "Running...")[:50]

    status_msg = (
        f"{BOT_EMOJI} **{BOT_NAME} Status**\n\n"
        f"🟢 Online\n"
        f"⏱️ Uptime: {uptime}\n"
        f"📅 Date: {now.strftime('%Y-%m-%d')}\n"
        f"🕐 Time: {now.strftime('%H:%M %Z')}\n"
        f"📝 Commands today: {len([c for c in command_history if c.get('date') == get_today_date()])}\n"
        f"🔄 Current task: {task_status}"
    )

    await update.message.reply_text(status_msg, parse_mode=ParseMode.MARKDOWN)


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /history command."""
    if not is_authorized(update.effective_user.id):
        return

    if not command_history:
        await update.message.reply_text(f"{BOT_EMOJI} No command history yet.")
        return

    history_msg = f"{BOT_EMOJI} **Recent Commands**\n\n"
    for i, cmd in enumerate(command_history[-10:], 1):
        status = "✅" if cmd.get("success") else "❌"
        text = cmd.get("text", "")[:50]
        history_msg += f"{i}. {status} {text}...\n"

    await update.message.reply_text(history_msg, parse_mode=ParseMode.MARKDOWN)


async def cmd_heartbeat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /heartbeat command - force a heartbeat check."""
    if not is_authorized(update.effective_user.id):
        return

    await update.message.reply_text(f"{BOT_EMOJI} Running heartbeat check...")

    async def send_callback(text):
        await update.message.reply_text(text)

    await run_heartbeat(send_callback)


async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /memory command."""
    if not is_authorized(update.effective_user.id):
        return

    from memory_manager import read_today_memory

    memory = read_today_memory()
    if not memory:
        await update.message.reply_text(f"{BOT_EMOJI} No memory entries for today yet.")
        return

    # Truncate if too long
    if len(memory) > 3000:
        memory = memory[:3000] + "\n\n... (truncated)"

    await update.message.reply_text(f"{BOT_EMOJI} **Today's Memory**\n\n{memory}", parse_mode=ParseMode.MARKDOWN)


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cancel command - actually kills the running process."""
    if not is_authorized(update.effective_user.id):
        return

    global current_task

    # Try to cancel the actual process
    success, message = await cancel_current_task()

    if success:
        current_task = {}
        await update.message.reply_text(f"{BOT_EMOJI} {message}")
    else:
        # Check if there's a tracked task even if no process
        if current_task:
            current_task = {}
            await update.message.reply_text(f"{BOT_EMOJI} Task state cleared (process may have already finished).")
        else:
            await update.message.reply_text(f"{BOT_EMOJI} {message}")


async def cmd_savememory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /savememory command - save a summary to long-term memory."""
    if not is_authorized(update.effective_user.id):
        return

    # Get the summary text from the command args
    summary = " ".join(context.args) if context.args else None

    if not summary:
        await update.message.reply_text(
            f"{BOT_EMOJI} Usage: /savememory <summary text>\n\n"
            f"Example: /savememory Decided to use Next.js for the new project"
        )
        return

    success = await save_conversation_summary(summary)
    if success:
        await update.message.reply_text(f"{BOT_EMOJI} ✅ Saved to memory:\n\n{summary}")
    else:
        await update.message.reply_text(f"{BOT_EMOJI} ❌ Failed to save to memory")


async def cmd_viewhistory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /viewhistory command - view recent conversation history."""
    if not is_authorized(update.effective_user.id):
        return

    history = get_conversation_history()
    if not history:
        await update.message.reply_text(f"{BOT_EMOJI} No conversation history yet.")
        return

    msg = f"{BOT_EMOJI} **Recent Conversation History** ({len(history)} messages)\n\n"
    for item in history[-10:]:  # Last 10 messages
        role = "You" if item["role"] == "user" else "Kiyomi"
        content = item["content"][:100] + "..." if len(item["content"]) > 100 else item["content"]
        timestamp = item.get("timestamp", "")[:16]
        msg += f"**{role}** ({timestamp}):\n{content}\n\n"

    await send_long_message(update, msg)


async def cmd_clearhistory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /clearhistory command - clear conversation history."""
    if not is_authorized(update.effective_user.id):
        return

    success = clear_conversation_history()
    if success:
        await update.message.reply_text(f"{BOT_EMOJI} ✅ Conversation history cleared.")
    else:
        await update.message.reply_text(f"{BOT_EMOJI} ❌ Failed to clear history")


# ============================================
# SUB-AGENT COMMANDS
# ============================================

async def cmd_spawn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /spawn command - spawn a sub-agent for background work."""
    if not is_authorized(update.effective_user.id):
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            f"{BOT_EMOJI} Usage: /spawn <task_id> <task description>\n\n"
            f"Example: /spawn podcast-script Write the midweek meeting podcast script"
        )
        return

    task_id = context.args[0]
    task_description = " ".join(context.args[1:])

    await update.message.reply_text(f"{BOT_EMOJI} Spawning sub-agent '{task_id}'...")

    success, message = await spawn_subagent(task_id, task_description)

    if success:
        await update.message.reply_text(f"{BOT_EMOJI} ✅ {message}")
    else:
        await update.message.reply_text(f"{BOT_EMOJI} ❌ {message}")


async def cmd_agents(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /agents command - list running sub-agents."""
    if not is_authorized(update.effective_user.id):
        return

    agents = list_running_subagents()

    if not agents:
        await update.message.reply_text(f"{BOT_EMOJI} No sub-agents currently running.")
        return

    msg = f"{BOT_EMOJI} **Running Sub-Agents**\n\n"
    for agent in agents:
        msg += f"• `{agent['task_id']}` (PID: {agent['pid']})\n"

    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def cmd_agentstatus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /agentstatus command - get status of a sub-agent."""
    if not is_authorized(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            f"{BOT_EMOJI} Usage: /agentstatus <task_id>"
        )
        return

    task_id = context.args[0]
    status = await get_subagent_status(task_id)

    if not status:
        await update.message.reply_text(f"{BOT_EMOJI} No sub-agent found with ID '{task_id}'")
        return

    msg = f"{BOT_EMOJI} **Sub-Agent Status: {task_id}**\n\n"
    msg += f"**Status:** {status['status']}\n"

    if status['status'] == 'running':
        msg += f"**PID:** {status['pid']}\n"
    else:
        msg += f"**Log:** {status.get('log_file', 'N/A')}\n"
        if 'log_tail' in status:
            log_preview = status['log_tail'][-500:]
            msg += f"\n**Recent output:**\n```\n{log_preview}\n```"

    await send_long_message(update, msg)


async def cmd_cancelagent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cancelagent command - cancel a running sub-agent."""
    if not is_authorized(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            f"{BOT_EMOJI} Usage: /cancelagent <task_id>"
        )
        return

    task_id = context.args[0]
    success, message = await cancel_subagent(task_id)

    if success:
        await update.message.reply_text(f"{BOT_EMOJI} ✅ {message}")
    else:
        await update.message.reply_text(f"{BOT_EMOJI} ❌ {message}")


async def cmd_learn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /learn command - force a learning cycle and show status."""
    if not is_authorized(update.effective_user.id):
        return

    await update.message.reply_text(f"{BOT_EMOJI} 🧠 Running learning cycle...")

    insights = await force_learning_cycle()
    status = get_learning_status()

    msg = f"{BOT_EMOJI} **Learning Status**\n\n"
    msg += f"**Last learned:** {status['last_learning'] or 'Never'}\n"
    msg += f"**Currently learning:** {'Yes' if status['is_learning'] else 'No'}\n\n"
    msg += f"**Insights:**\n{insights}"

    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


# ============================================
# REMINDER COMMANDS
# ============================================

async def cmd_remind(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /remind command - set a reminder."""
    if not is_authorized(update.effective_user.id):
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            f"{BOT_EMOJI} **Set a Reminder**\n\n"
            f"Usage: /remind <when> <message>\n\n"
            f"**Examples:**\n"
            f"`/remind in 30 minutes Check on the build`\n"
            f"`/remind in 2 hours Review PR`\n"
            f"`/remind tomorrow at 9am Morning standup`\n"
            f"`/remind at 3pm Call with client`\n",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Parse the time and message
    full_text = " ".join(context.args)

    # Try to find where the time ends and message begins
    time_keywords = ["in ", "at ", "tomorrow"]
    message_start = len(full_text)

    # Find the message part (after time specification)
    for i, word in enumerate(context.args):
        if i > 0:  # Skip first word
            if word not in ["in", "at", "tomorrow", "minutes", "minute", "hours", "hour", "am", "pm"]:
                # Check if previous words form a valid time
                time_part = " ".join(context.args[:i])
                if any(kw in time_part.lower() for kw in time_keywords):
                    message_part = " ".join(context.args[i:])
                    remind_time = parse_reminder_time(time_part)
                    if remind_time:
                        reminder_id = add_reminder(message_part, remind_time)
                        await update.message.reply_text(
                            f"{BOT_EMOJI} ⏰ Reminder set!\n\n"
                            f"**When:** {remind_time.strftime('%Y-%m-%d %H:%M')}\n"
                            f"**Message:** {message_part}\n"
                            f"**ID:** `{reminder_id}`",
                            parse_mode=ParseMode.MARKDOWN
                        )
                        return
                    break

    await update.message.reply_text(
        f"{BOT_EMOJI} Couldn't parse that time. Try:\n"
        f"`/remind in 30 minutes <message>`\n"
        f"`/remind tomorrow at 9am <message>`",
        parse_mode=ParseMode.MARKDOWN
    )


async def cmd_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /reminders command - list all reminders."""
    if not is_authorized(update.effective_user.id):
        return

    reminders = list_reminders()

    if not reminders:
        await update.message.reply_text(f"{BOT_EMOJI} No pending reminders.")
        return

    msg = f"{BOT_EMOJI} **Pending Reminders**\n\n"
    for r in reminders[:10]:  # Max 10
        status = "🔔" if r.get("is_due") else "⏰"
        repeat = f" (repeats {r['repeat']})" if r.get("repeat") else ""
        msg += f"{status} **{r['remind_at_formatted']}**{repeat}\n"
        msg += f"   {r['message'][:50]}{'...' if len(r['message']) > 50 else ''}\n"
        msg += f"   ID: `{r['id']}`\n\n"

    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def cmd_cancelremind(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cancelremind command - remove a reminder."""
    if not is_authorized(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            f"{BOT_EMOJI} Usage: /cancelremind <reminder_id>\n\n"
            f"Use /reminders to see IDs"
        )
        return

    reminder_id = context.args[0]
    if remove_reminder(reminder_id):
        await update.message.reply_text(f"{BOT_EMOJI} ✅ Reminder cancelled")
    else:
        await update.message.reply_text(f"{BOT_EMOJI} ❌ Reminder not found")


# ============================================
# WEB TOOLS COMMANDS
# ============================================

async def cmd_weather(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /weather command - get weather info."""
    if not is_authorized(update.effective_user.id):
        return

    location = " ".join(context.args) if context.args else "Atlanta, GA"
    await update.message.reply_text(f"{BOT_EMOJI} 🌤️ Getting weather for {location}...")

    weather = await get_weather(location)
    if weather:
        await update.message.reply_text(f"🌸 {weather}")
    else:
        await update.message.reply_text(f"{BOT_EMOJI} ❌ Couldn't get weather")


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /search command - web search."""
    if not is_authorized(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            f"{BOT_EMOJI} Usage: /search <query>"
        )
        return

    query = " ".join(context.args)
    await update.message.reply_text(f"{BOT_EMOJI} 🔍 Searching for: {query}...")

    results = await web_search(query, num_results=5)
    if results:
        msg = f"🌸 **Search Results**\n\n"
        for i, r in enumerate(results, 1):
            msg += f"{i}. **{r['title']}**\n   {r['url']}\n\n"
        await send_long_message(update, msg)
    else:
        await update.message.reply_text(f"{BOT_EMOJI} ❌ No results found")


async def cmd_fetch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /fetch command - fetch URL content."""
    if not is_authorized(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            f"{BOT_EMOJI} Usage: /fetch <url>"
        )
        return

    url = context.args[0]
    await update.message.reply_text(f"{BOT_EMOJI} 🌐 Fetching {url}...")

    result = await web_fetch(url)
    if result["status"] == "success":
        content = result["content"][:2000]
        if len(result["content"]) > 2000:
            content += "\n\n... (truncated)"
        msg = f"🌸 **{result['title'] or url}**\n\n{content}"
        await send_long_message(update, msg)
    else:
        await update.message.reply_text(f"{BOT_EMOJI} ❌ {result.get('error', 'Fetch failed')}")


async def cmd_skills(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /skills command - list available skills."""
    if not is_authorized(update.effective_user.id):
        return

    skills = list_available_skills()
    if not skills:
        await update.message.reply_text(f"{BOT_EMOJI} No skills found")
        return

    msg = f"{BOT_EMOJI} **Available Skills** ({len(skills)} total)\n\n"
    for skill in skills[:20]:  # Max 20
        desc = skill.get("description", "")[:50]
        msg += f"• `{skill['name']}` - {desc}\n"

    await send_long_message(update, msg)


async def cmd_dailytext(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /dailytext command - get today's daily text."""
    if not is_authorized(update.effective_user.id):
        return

    await update.message.reply_text(f"{BOT_EMOJI} 📖 Fetching daily text...")

    text = await get_daily_text()
    if text:
        await send_long_message(update, f"🌸 **Daily Text**\n\n{text}")
    else:
        await update.message.reply_text(f"{BOT_EMOJI} ❌ Couldn't fetch daily text")


async def cmd_factory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /factory command - toggle factory mode."""
    if not is_authorized(update.effective_user.id):
        return

    if is_factory_mode():
        from proactive import disable_factory_mode
        disable_factory_mode()
        await update.message.reply_text(f"{BOT_EMOJI} 🏭 Factory mode disabled")
    else:
        enable_factory_mode()
        await update.message.reply_text(
            f"{BOT_EMOJI} 🏭 **Factory mode activated**\n\n"
            f"I'll work through the night:\n"
            f"• Executing tasks in HEARTBEAT.md\n"
            f"• Spawning agents for long work\n"
            f"• Reporting results in morning brief\n\n"
            f"Use /factory again to disable."
        )


# ============================================
# QUICK PROJECT COMMANDS
# ============================================

async def cmd_deploy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /deploy <project> - quick deploy a project."""
    if not is_authorized(update.effective_user.id):
        return

    if not context.args:
        # Show deployable projects
        projects = list_projects()
        deployable = [p for p in projects if "vercel" in p.deploy_cmd.lower()]
        msg = f"{BOT_EMOJI} **Deployable Projects**\n\n"
        for p in deployable:
            msg += f"• `{p.name.lower().replace(' ', '-')}` - {p.url or 'No URL'}\n"
        msg += f"\nUsage: `/deploy <project-name>`"
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        return

    project_name = " ".join(context.args)
    project = get_project_by_name(project_name)

    if not project:
        await update.message.reply_text(f"{BOT_EMOJI} ❌ Project not found: {project_name}")
        return

    await update.message.reply_text(f"{BOT_EMOJI} 🚀 Deploying {project.name}...")

    async def send_update(msg):
        await update.message.reply_text(f"🌸 {msg}")

    result = await smart_deploy(project, send_update)

    if result.success:
        await update.message.reply_text(
            f"{BOT_EMOJI} ✅ **Deployed!**\n\n"
            f"**URL:** {result.url}\n"
            f"**Verified:** {'Yes' if result.verified else 'No'}",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(f"{BOT_EMOJI} ❌ Deploy failed: {result.message}")


async def cmd_logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /logs <project> - get Vercel logs."""
    if not is_authorized(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(f"{BOT_EMOJI} Usage: /logs <project-name>")
        return

    project_name = " ".join(context.args)
    project = get_project_by_name(project_name)

    if not project:
        await update.message.reply_text(f"{BOT_EMOJI} ❌ Project not found: {project_name}")
        return

    await update.message.reply_text(f"{BOT_EMOJI} 📋 Getting logs for {project.name}...")

    success, logs = await get_vercel_logs(project)

    if success:
        # Truncate if too long
        if len(logs) > 3000:
            logs = logs[:3000] + "\n\n... (truncated)"
        await send_long_message(update, f"**{project.name} Logs:**\n```\n{logs}\n```")
    else:
        await update.message.reply_text(f"{BOT_EMOJI} ❌ {logs}")


async def cmd_rollback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /rollback <project> - rollback to previous deployment."""
    if not is_authorized(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(f"{BOT_EMOJI} Usage: /rollback <project-name>")
        return

    project_name = " ".join(context.args)
    project = get_project_by_name(project_name)

    if not project:
        await update.message.reply_text(f"{BOT_EMOJI} ❌ Project not found: {project_name}")
        return

    await update.message.reply_text(f"{BOT_EMOJI} ⏪ Rolling back {project.name}...")

    async def send_update(msg):
        await update.message.reply_text(f"🌸 {msg}")

    success, message = await rollback_vercel(project, send_update)

    if success:
        await update.message.reply_text(f"{BOT_EMOJI} ✅ {message}")
    else:
        await update.message.reply_text(f"{BOT_EMOJI} ❌ {message}")


async def cmd_projects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /projects - list all projects."""
    if not is_authorized(update.effective_user.id):
        return

    projects = list_projects()
    msg = f"{BOT_EMOJI} **Richard's Projects**\n\n"

    for p in projects:
        url_str = f" - [{p.url}]({p.url})" if p.url else ""
        msg += f"**{p.name}**{url_str}\n"
        msg += f"  Tech: {p.tech}\n"
        msg += f"  Path: `{p.path}`\n\n"

    await send_long_message(update, msg)


async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /check <project> - check if a project's site is up."""
    if not is_authorized(update.effective_user.id):
        return

    if not context.args:
        # Run full status check
        await update.message.reply_text(f"{BOT_EMOJI} 🔍 Checking all sites...")
        report = generate_status_report()
        await update.message.reply_text(f"🌸 {report}", parse_mode=ParseMode.MARKDOWN)
        return

    project_name = " ".join(context.args)
    project = get_project_by_name(project_name)

    if not project or not project.url:
        await update.message.reply_text(f"{BOT_EMOJI} ❌ Project not found or has no URL")
        return

    await update.message.reply_text(f"{BOT_EMOJI} 🔍 Checking {project.name}...")
    result = await quick_check(project.url)
    await update.message.reply_text(f"🌸 **{project.name}:** {result}")


async def cmd_gitstatus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /gitstatus <project> - check git status."""
    if not is_authorized(update.effective_user.id):
        return

    if not context.args:
        # Use current project
        current = get_current_project_name()
        if current:
            project = get_project_by_name(current)
        else:
            await update.message.reply_text(f"{BOT_EMOJI} Usage: /gitstatus <project-name>")
            return
    else:
        project_name = " ".join(context.args)
        project = get_project_by_name(project_name)

    if not project:
        await update.message.reply_text(f"{BOT_EMOJI} ❌ Project not found")
        return

    success, status = await git_status(project)

    if success:
        await update.message.reply_text(
            f"{BOT_EMOJI} **Git Status - {project.name}**\n```\n{status}\n```",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(f"{BOT_EMOJI} ❌ {status}")


# ============================================
# SWARM COMMANDS
# ============================================

async def cmd_swarm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /swarm command - spawn a swarm for a complex task."""
    if not is_authorized(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            f"{BOT_EMOJI} **Swarm Intelligence**\n\n"
            f"Usage: `/swarm <complex task>`\n\n"
            f"I'll automatically decompose the task and spawn multiple agents.\n\n"
            f"Example:\n"
            f"`/swarm update all projects to use the new footer`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    task = " ".join(context.args)
    await update.message.reply_text(f"{BOT_EMOJI} 🐝 Analyzing task for swarm decomposition...")

    from swarm import decompose_task

    async def send_update(msg):
        await update.message.reply_text(f"🌸 {msg}", parse_mode=ParseMode.MARKDOWN)

    # Decompose the task
    subtasks = await decompose_task(task)

    if len(subtasks) <= 1:
        await update.message.reply_text(
            f"{BOT_EMOJI} This task doesn't need a swarm - it's simple enough for one agent.\n"
            f"Processing normally..."
        )
        # Execute normally
        result, success = await execute_claude(task, check_for_swarm=False)
        await send_long_message(update, result)
        return

    # Spawn the swarm
    swarm = await spawn_swarm(task, subtasks, send_update)
    await update.message.reply_text(
        f"{BOT_EMOJI} ✅ Swarm `{swarm.swarm_id}` deployed!\n\n"
        f"**Agents:** {len(subtasks)}\n"
        f"**Subtasks:**\n" + "\n".join(f"• {t[:50]}..." for t in subtasks),
        parse_mode=ParseMode.MARKDOWN
    )


async def cmd_swarms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /swarms command - list active swarms."""
    if not is_authorized(update.effective_user.id):
        return

    swarms = get_active_swarms()

    if not swarms:
        await update.message.reply_text(f"{BOT_EMOJI} No active swarms.")
        return

    msg = f"{BOT_EMOJI} **Active Swarms**\n\n"
    for s in swarms:
        msg += f"**{s['swarm_id']}**\n"
        msg += f"  Status: {s['status']}\n"
        msg += f"  Agents: {s['completed']}/{s['agents']} complete\n"
        msg += f"  Task: {s['master_task']}...\n\n"

    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


# ============================================
# SELF-UPDATE COMMANDS
# ============================================

async def cmd_update_self(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /updateself command - request a self-update."""
    if not is_authorized(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            f"{BOT_EMOJI} **Self-Update**\n\n"
            f"Usage: `/updateself <feature request>`\n\n"
            f"Example:\n"
            f"`/updateself add a command to check disk space`\n\n"
            f"I'll generate the code, validate it, backup the old version, and apply the update.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    request = " ".join(context.args)
    await update.message.reply_text(f"{BOT_EMOJI} 🔧 Processing self-update request...")

    success, result = await process_self_update_request(request)

    if success:
        await update.message.reply_text(
            f"{BOT_EMOJI} ✅ **Update Applied!**\n\n{result}\n\n"
            f"Use `/restart` to apply changes.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(f"{BOT_EMOJI} ❌ Update failed: {result}")


async def cmd_restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /restart command - restart Kiyomi."""
    if not is_authorized(update.effective_user.id):
        return

    await update.message.reply_text(f"{BOT_EMOJI} 🔄 Restarting... I'll be back in a few seconds!")

    success, message = await restart_keiko()

    if not success:
        await update.message.reply_text(f"{BOT_EMOJI} ❌ {message}")


async def cmd_backups(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /backups command - list recent backups."""
    if not is_authorized(update.effective_user.id):
        return

    file_name = context.args[0] if context.args else "bot.py"

    backups = get_recent_backups(file_name)

    if not backups:
        await update.message.reply_text(f"{BOT_EMOJI} No backups found for {file_name}")
        return

    msg = f"{BOT_EMOJI} **Recent Backups for {file_name}**\n\n"
    for b in backups:
        msg += f"• `{b.name}` ({b.stat().st_size} bytes)\n"

    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def cmd_update_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /updatehistory command - show self-update history."""
    if not is_authorized(update.effective_user.id):
        return

    history = get_update_history(10)

    if not history:
        await update.message.reply_text(f"{BOT_EMOJI} No update history yet.")
        return

    msg = f"{BOT_EMOJI} **Recent Self-Updates**\n\n"
    for h in history[-10:]:
        timestamp = h.get("timestamp", "")[:16]
        file = h.get("file", "unknown")
        desc = h.get("description", "")[:50]
        msg += f"• **{timestamp}** - {file}\n  _{desc}_\n\n"

    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


# ============================================
# ESCALATION COMMANDS
# ============================================

async def cmd_escalations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /escalations command - show escalation stats."""
    if not is_authorized(update.effective_user.id):
        return

    stats = get_escalation_stats()
    recent = get_recent_escalations(5)

    msg = f"{BOT_EMOJI} **Escalation Stats**\n\n"
    msg += f"**Total:** {stats.get('total', 0)}\n"
    msg += f"**Escalated to you:** {stats.get('escalated', 0)}\n"
    msg += f"**Auto-fixed:** {stats.get('auto_fixed', 0)}\n"
    msg += f"**Auto-fix rate:** {stats.get('auto_fix_rate', '0%')}\n\n"

    if stats.get("by_type"):
        msg += "**By Type:**\n"
        for t, c in stats["by_type"].items():
            msg += f"• {t}: {c}\n"

    if recent:
        msg += "\n**Recent:**\n"
        for r in recent:
            status = "✅" if r["resolved"] else ("🚨" if r["escalated"] else "⏳")
            msg += f"{status} {r['title'][:40]}...\n"

    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


# ============================================
# PREFERENCES COMMANDS
# ============================================

async def cmd_preferences(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /preferences command - show learned preferences."""
    if not is_authorized(update.effective_user.id):
        return

    prefs = get_all_preferences()
    stats = get_correction_stats()

    msg = f"{BOT_EMOJI} **Learned Preferences**\n\n"
    msg += f"_Total corrections learned: {stats.get('total', 0)}_\n"
    msg += f"_This week: {stats.get('recent_week', 0)}_\n\n"

    for category, pref_list in prefs.items():
        if pref_list:
            msg += f"**{category.title()}:**\n"
            for p in pref_list[-5:]:
                msg += f"• {p}\n"
            msg += "\n"

    if not any(prefs.values()):
        msg += "_No preferences learned yet. Just correct me and I'll remember!_"

    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


# ============================================
# COST TRACKING COMMANDS
# ============================================

async def cmd_costs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /costs command - show API cost report."""
    if not is_authorized(update.effective_user.id):
        return

    report = generate_cost_report()
    await update.message.reply_text(report, parse_mode=ParseMode.MARKDOWN)


async def cmd_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /budget command - set daily budget."""
    if not is_authorized(update.effective_user.id):
        return

    if not context.args:
        settings = get_alert_settings()
        daily = settings.get("daily", {})
        current_spend = get_daily_cost()

        await update.message.reply_text(
            f"{BOT_EMOJI} **Budget Settings**\n\n"
            f"**Daily limit:** ${daily.get('threshold', 10):.2f}\n"
            f"**Today's spend:** ${current_spend:.2f}\n\n"
            f"Usage: `/budget <amount>` to set daily limit",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    try:
        amount = float(context.args[0].replace("$", ""))
        if set_daily_budget(amount):
            await update.message.reply_text(
                f"{BOT_EMOJI} ✅ Daily budget set to ${amount:.2f}"
            )
        else:
            await update.message.reply_text(f"{BOT_EMOJI} ❌ Failed to set budget")
    except ValueError:
        await update.message.reply_text(f"{BOT_EMOJI} Invalid amount. Use: /budget 15.00")


# ============================================
# SESSION COMMANDS
# ============================================

async def cmd_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /session command - show current session info."""
    if not is_authorized(update.effective_user.id):
        return

    summary = get_session_summary()
    if summary:
        await update.message.reply_text(
            f"{BOT_EMOJI} {summary}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_continue_keyboard()
        )
    else:
        await update.message.reply_text(
            f"{BOT_EMOJI} No active session.\n\n"
            f"Start working on something and I'll track it!",
            reply_markup=build_quick_actions_keyboard()
        )


async def cmd_mcps(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /mcps command - list available MCP servers."""
    if not is_authorized(update.effective_user.id):
        return

    mcp_list = format_mcp_list()
    await update.message.reply_text(
        f"{BOT_EMOJI} {mcp_list}",
        parse_mode=ParseMode.MARKDOWN
    )


# ============================================
# PLUGIN COMMANDS
# ============================================

async def cmd_plugins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /plugins command - list loaded plugins."""
    if not is_authorized(update.effective_user.id):
        return

    plugin_list = format_plugin_list()
    await update.message.reply_text(
        f"{BOT_EMOJI} {plugin_list}",
        parse_mode=ParseMode.MARKDOWN
    )


async def cmd_reload_plugin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /reloadplugin command - reload a plugin."""
    if not is_authorized(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            f"{BOT_EMOJI} Usage: `/reloadplugin <plugin_name>`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    plugin_name = context.args[0]
    await update.message.reply_text(f"{BOT_EMOJI} Reloading plugin '{plugin_name}'...")

    success, message = await reload_plugin(plugin_name)

    if success:
        await update.message.reply_text(f"{BOT_EMOJI} ✅ {message}")
    else:
        await update.message.reply_text(f"{BOT_EMOJI} ❌ {message}")


async def cmd_skillslist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /skillslist command - list all available skills."""
    if not is_authorized(update.effective_user.id):
        return

    skill_list = format_skill_list()
    await send_long_message(update, f"{BOT_EMOJI} {skill_list}")


async def cmd_health(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /health command - show system health."""
    if not is_authorized(update.effective_user.id):
        return

    health = get_health_status()
    conn = get_connection_status()
    uptime = get_uptime()

    status = "🟢 Healthy" if health.get("healthy", True) else "🔴 Issues Detected"

    msg = f"{BOT_EMOJI} **System Health**\n\n"
    msg += f"**Status:** {status}\n"
    msg += f"**Uptime:** {uptime}\n\n"

    msg += "**Metrics:**\n"
    metrics = health.get("metrics", {})
    if "memory_mb" in metrics:
        msg += f"  • Memory: {metrics['memory_mb']}MB\n"
    if "cpu_percent" in metrics:
        msg += f"  • CPU: {metrics['cpu_percent']}%\n"
    if "log_size_mb" in metrics:
        msg += f"  • Log size: {metrics['log_size_mb']}MB\n"

    if health.get("issues"):
        msg += f"\n**Issues:**\n"
        for issue in health["issues"]:
            msg += f"  ⚠️ {issue}\n"

    msg += f"\n**Connections:**\n"
    msg += f"  • Telegram: {'🟢' if conn['telegram']['connected'] else '🔴'}\n"
    msg += f"  • Claude: {'🟢' if conn['claude']['connected'] else '🔴'}\n"

    # Supervised background tasks
    supervised = task_supervisor.status()
    if supervised:
        msg += f"\n**Background Tasks ({len(supervised)}):**\n"
        for t in supervised:
            icon = "🟢" if t["running"] else "🔴"
            restarts = f" (restarts: {t['restarts']})" if t["restarts"] > 0 else ""
            msg += f"  {icon} {t['name']}{restarts}\n"
            if t["last_error"]:
                msg += f"      ↳ {t['last_error'][:60]}\n"

    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


# ============================================
# COMPUTER USE COMMANDS
# ============================================

async def cmd_computer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /computer command - control the computer."""
    if not is_authorized(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            f"{BOT_EMOJI} **Computer Use**\n\n"
            "Control the Mac Mini's screen, mouse, and keyboard.\n\n"
            "**Usage:**\n"
            "`/computer <task description>`\n\n"
            "**Examples:**\n"
            "• `/computer Open Safari and search for weather in Austin`\n"
            "• `/computer Open Mail and compose a new email`\n"
            "• `/computer Take a screenshot`\n\n"
            "I'll control the screen and show you progress!",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    task = " ".join(context.args)

    async def send_progress(msg):
        await update.message.reply_text(msg)

    await update.message.reply_text(f"{BOT_EMOJI} 🖥️ Starting computer task...")

    success, result = await run_computer_task(task, send_callback=send_progress)

    if not success:
        await update.message.reply_text(f"❌ Task may be incomplete: {result[:500]}")


async def cmd_browse(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /browse command - open URL or search."""
    if not is_authorized(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            f"{BOT_EMOJI} **Browse Web**\n\n"
            "**Usage:**\n"
            "• `/browse <url>` - Open a URL\n"
            "• `/browse search <query>` - Search and summarize results\n\n"
            "**Examples:**\n"
            "• `/browse https://github.com`\n"
            "• `/browse search best restaurants in Austin`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    query = " ".join(context.args)

    async def send_progress(msg):
        await update.message.reply_text(msg)

    if query.startswith("http"):
        # Open URL directly
        await update.message.reply_text(f"{BOT_EMOJI} 🌐 Opening {query}...")
        success, result = await open_url(query)
        await update.message.reply_text(result)
    elif query.lower().startswith("search "):
        # Web research workflow
        search_query = query[7:]  # Remove "search "
        await update.message.reply_text(f"{BOT_EMOJI} 🔍 Researching: {search_query}...")
        success, result = await web_research_workflow(search_query, send_callback=send_progress)
    else:
        # Treat as URL or search
        if "." in query and " " not in query:
            await update.message.reply_text(f"{BOT_EMOJI} 🌐 Opening {query}...")
            success, result = await open_url(f"https://{query}")
            await update.message.reply_text(result)
        else:
            await update.message.reply_text(f"{BOT_EMOJI} 🔍 Researching: {query}...")
            success, result = await web_research_workflow(query, send_callback=send_progress)


async def cmd_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /email command - send an email."""
    if not is_authorized(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            f"{BOT_EMOJI} **Send Email**\n\n"
            "**Usage:**\n"
            "`/email <to> | <subject> | <body>`\n\n"
            "**Example:**\n"
            "`/email john@example.com | Meeting Tomorrow | Hi John, just confirming our meeting at 2pm.`\n\n"
            "I'll open Mail and send it for you!",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    email_text = " ".join(context.args)

    # Parse email parts (separated by |)
    parts = [p.strip() for p in email_text.split("|")]

    if len(parts) < 3:
        await update.message.reply_text(
            "❌ Please use format: `/email to | subject | body`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    to = parts[0]
    subject = parts[1]
    body = " | ".join(parts[2:])  # Body can contain |

    async def send_progress(msg):
        await update.message.reply_text(msg)

    await update.message.reply_text(f"{BOT_EMOJI} 📧 Composing email to {to}...")

    success, result = await send_email_workflow(to, subject, body, send_callback=send_progress)


async def cmd_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /screenshot command - take and send a screenshot."""
    if not is_authorized(update.effective_user.id):
        return

    from computer_use import take_screenshot
    from pathlib import Path

    await update.message.reply_text(f"{BOT_EMOJI} 📸 Taking screenshot...")

    try:
        base64_data, filepath = take_screenshot()

        # Send the screenshot as a photo
        with open(filepath, "rb") as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=f"Screenshot taken at {datetime.now().strftime('%H:%M:%S')}"
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Screenshot failed: {e}")


async def cmd_openapp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /openapp command - open a macOS application."""
    if not is_authorized(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            f"{BOT_EMOJI} **Open Application**\n\n"
            "**Usage:** `/openapp <app name>`\n\n"
            "**Examples:**\n"
            "• `/openapp Safari`\n"
            "• `/openapp Mail`\n"
            "• `/openapp Finder`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    app_name = " ".join(context.args)

    await update.message.reply_text(f"{BOT_EMOJI} 🚀 Opening {app_name}...")

    success, result = await open_application(app_name)
    await update.message.reply_text(result)


# ============================================
# MESSAGE HANDLER
# ============================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages."""
    global current_task, pending_confirmations, last_kiyomi_response

    user_id = update.effective_user.id

    # Security check - silent reject unauthorized users
    if not is_authorized(user_id):
        logger.warning(f"Unauthorized access attempt from user {user_id}")
        return

    # Update activity tracker
    update_last_message_time()
    update_last_richard_message()  # Track for proactive features
    record_activity()  # Watchdog activity tracking

    text = update.message.text.strip()
    if not text:
        return

    logger.info(f"Message from Richard: {sanitize_for_logging(text)[:100]}")

    # Check for "continue" command - resume previous session
    if is_continue_command(text):
        if should_continue():
            prompt = get_continue_prompt()
            summary = get_session_summary()
            await update.message.reply_text(
                f"{BOT_EMOJI} ▶️ Resuming...\n\n{summary}",
                reply_markup=build_continue_keyboard()
            )
            # Execute the continuation
            result, success = await execute_claude(prompt, last_response=last_kiyomi_response)
            await send_long_message(update, result)
            return
        else:
            await update.message.reply_text(f"{BOT_EMOJI} No previous task to continue.")
            return

    # Analyze the task for smart response
    analysis = analyze_task(text, last_kiyomi_response)

    # Check if clarification is needed
    needs_clarification, question = should_ask_clarification(analysis)
    if needs_clarification and question:
        await update.message.reply_text(f"{BOT_EMOJI} {question}")
        return

    # Check for confirmation response
    if user_id in pending_confirmations:
        if text.lower() in ["yes", "y", "confirm"]:
            original_cmd = pending_confirmations.pop(user_id)
            text = original_cmd
        elif text.lower() in ["no", "n", "cancel"]:
            pending_confirmations.pop(user_id)
            await update.message.reply_text(f"{BOT_EMOJI} Cancelled.")
            return
        else:
            # Not a confirmation response, process as new message
            pending_confirmations.pop(user_id, None)

    # Check plugins for triggers
    plugin_context = {"user_id": user_id, "chat_id": update.effective_chat.id}
    plugin_response = await dispatch_trigger(text, plugin_context)
    if plugin_response:
        await update.message.reply_text(f"{BOT_EMOJI} {plugin_response}")
        return

    # Natural command parser DISABLED — intercepted normal conversation
    # All messages go straight to Claude now
    # natural_cmd = parse_natural_command(text)
    # if natural_cmd:
    # cmd_type, cmd_arg = natural_cmd

    # async def send_cb(msg):
    # await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    # # Handle spawn separately (needs executor)
    # if cmd_type == "spawn":
    # # Generate task ID from first few words
    # task_id = "-".join(cmd_arg.split()[:3]).lower()[:20]
    # success, message = await spawn_subagent(task_id, cmd_arg)
    # if success:
    # await update.message.reply_text(f"{BOT_EMOJI} ✅ {message}")
    # else:
    # await update.message.reply_text(f"{BOT_EMOJI} ❌ {message}")
    # return

    # # Handle screenshot separately (needs to send image)
    # if cmd_type == "screenshot":
    # from computer_use import take_screenshot
    # await update.message.reply_text(f"{BOT_EMOJI} 📸 Taking screenshot...")
    # try:
    # base64_data, filepath = take_screenshot()
    # with open(filepath, "rb") as photo:
    # await update.message.reply_photo(
    # photo=photo,
    # caption=f"Screenshot taken at {datetime.now().strftime('%H:%M:%S')}"
    # )
    # # Log to history
    # command_history.append({
    # "text": f"[screenshot] {text}",
    # "success": True,
    # "date": get_today_date()
    # })
    # _save_command_history(command_history)
    # except Exception as e:
    # logger.error(f"Screenshot error: {e}")
    # await update.message.reply_text(f"{BOT_EMOJI} ❌ Screenshot failed: {str(e)[:100]}")
    # return

    # # Handle computer use tasks (browse, open apps, click, fill forms, etc.)
    # if cmd_type == "computer":
    # from computer_use import run_computer_task, take_screenshot

    # async def send_progress(msg):
    # # Don't use markdown to avoid parsing issues with URLs
    # await update.message.reply_text(msg)

    # try:
    # success, result = await run_computer_task(cmd_arg, send_callback=send_progress)

    # # Always take and send a screenshot after browser tasks
    # try:
    # await asyncio.sleep(1)  # Brief pause for page to settle
    # base64_data, filepath = take_screenshot()
    # with open(filepath, "rb") as photo:
    # # Craft a conversational caption
    # if success and result:
    # caption = f"🌸 Here's what I found! {result[:200]}" if len(result) < 200 else f"🌸 Done! Here's what it looks like."
    # else:
    # caption = "🌸 Here's what's on screen now"
    # await update.message.reply_photo(photo=photo, caption=caption[:1000])
    # except Exception as screenshot_error:
    # logger.error(f"Screenshot after task failed: {screenshot_error}")
    # # Still send the text result if screenshot fails
    # if success and result:
    # await update.message.reply_text(f"🌸 {result[:1000]}")

    # # Log to history
    # command_history.append({
    # "text": f"[computer] {text}",
    # "success": success,
    # "date": get_today_date()
    # })
    # _save_command_history(command_history)
    # except Exception as e:
    # logger.error(f"Computer task error: {e}")
    # await update.message.reply_text(f"🌸 Hmm, something went wrong: {str(e)[:200]}")
    # return

    # handled = await execute_natural_command(cmd_type, cmd_arg, send_cb)
    # if handled:
    # # Log to history
    # command_history.append({
    # "text": f"[{cmd_type}] {text}",
    # "success": True,
    # "date": get_today_date()
    # })
    # _save_command_history(command_history)
    # return

    # Blocked patterns check — let Claude handle safety
    # blocked = contains_blocked_pattern(text)

    # Confirmation check disabled — Claude handles safety
    # confirm_pattern = needs_confirmation(text)

    # Send typing indicator
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    # Removed confidence prefix — just show typing (feels more natural)
    # confidence_msg = get_confidence_prefix(analysis)
    # await update.message.reply_text(f"{BOT_EMOJI} {confidence_msg}")

    # Execute via Claude Code
    current_task = {"description": text, "started": datetime.now()}

    # Keep-alive typing indicator — re-send every 4 seconds so it never expires
    typing_active = True

    async def _keep_typing():
        while typing_active:
            try:
                await asyncio.sleep(4)
                if typing_active:
                    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            except Exception:
                pass  # Don't crash on typing errors

    typing_task = asyncio.create_task(_keep_typing())

    try:
        # Progress callback sends updates to the chat while working
        async def _progress_update(msg: str):
            try:
                await context.bot.send_message(chat_id=chat_id, text=msg)
            except Exception:
                pass

        result, success = await execute_claude(
            text,
            last_response=last_kiyomi_response,
            progress_callback=_progress_update,
        )

        # Update last response for future correction detection
        last_kiyomi_response = result

        # Log to history
        command_history.append({
            "text": text,
            "success": success,
            "date": get_today_date()
        })
        _save_command_history(command_history)

        # Log to memory
        log_command(text, result, success)

        # Send response
        if success:
            await send_long_message(update, result)
        else:
            await update.message.reply_text(f"❌ {result}")

    except Exception as e:
        logger.exception(f"Error handling message: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)[:200]}")

    finally:
        typing_active = False
        typing_task.cancel()
        current_task = {}


# ============================================
# MEDIA HANDLER
# ============================================

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photos, videos, voice messages, and documents - with AI processing."""
    if not is_authorized(update.effective_user.id):
        return

    update_last_message_time()
    caption = update.message.caption or ""

    # Handle voice messages - transcribe and process
    if update.message.voice:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        try:
            # Download voice file
            voice_file = await context.bot.get_file(update.message.voice.file_id)
            voice_path = BASE_DIR / "temp" / f"voice_{update.message.voice.file_id}.ogg"
            voice_path.parent.mkdir(exist_ok=True)
            await voice_file.download_to_drive(voice_path)

            # Transcribe with whisper (local, fast)
            import subprocess
            transcription = ""
            try:
                whisper_result = subprocess.run(
                    ["/Users/richardecholsai2/Library/Python/3.9/bin/whisper", str(voice_path), "--model", "base", "--output_format", "txt", "--output_dir", str(voice_path.parent)],
                    capture_output=True, text=True, timeout=120
                )
                txt_path = voice_path.with_suffix(".txt")
                if txt_path.exists():
                    transcription = txt_path.read_text().strip()
                    txt_path.unlink(missing_ok=True)
            except FileNotFoundError:
                # Whisper not installed — try OpenAI API as fallback
                try:
                    import openai
                    client = openai.OpenAI(api_key="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")
                    with open(voice_path, "rb") as audio_file:
                        resp = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
                    transcription = resp.text
                except Exception as api_err:
                    logger.error(f"OpenAI whisper fallback failed: {api_err}")
            except Exception as whisper_err:
                logger.error(f"Whisper transcription failed: {whisper_err}")

            if transcription:
                # Send transcription to Claude for response
                result, success = await execute_claude(
                    f"Richard sent a voice message. Here's what he said:\n\n\"{transcription}\"\n\nRespond to what he said."
                )
                if success:
                    await send_long_message(update, result)
                else:
                    await update.message.reply_text(f"{BOT_EMOJI} {transcription}\n\n(I heard you but couldn't process the request)")
            else:
                await update.message.reply_text(
                    f"{BOT_EMOJI} Couldn't understand the voice message. Could you type it out?"
                )

            # Cleanup
            voice_path.unlink(missing_ok=True)

        except Exception as e:
            logger.error(f"Voice processing error: {e}")
            await update.message.reply_text(
                f"{BOT_EMOJI} Voice processing failed. Please type your request."
            )
        return

    # Handle photos - download and analyze with vision
    if update.message.photo:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        try:
            # Get highest resolution photo
            photo = update.message.photo[-1]
            photo_file = await context.bot.get_file(photo.file_id)
            photo_path = BASE_DIR / "temp" / f"photo_{photo.file_id}.jpg"
            photo_path.parent.mkdir(exist_ok=True)
            await photo_file.download_to_drive(photo_path)

            # Build prompt with image context - ACTION ORIENTED
            prompt = f"Richard sent me a screenshot. The image is saved at: {photo_path}\n\n"
            if caption:
                prompt += f"His message: \"{caption}\"\n\n"

            prompt += """IMPORTANT - Be action-oriented like Claude Code:
1. Look at the image and identify what it shows (error message, UI issue, etc.)
2. Start your response by briefly stating what you see: "I see the error - [description]"
3. Then say what you'll do: "Let me check the code and fix it"
4. Actually go to the relevant project, find the issue, fix it, and deploy if needed
5. Report what you fixed and provide the URL if deployed

If this is an error screenshot, DIAGNOSE IT AND FIX IT. Don't just describe what you see - take action.
Use the project registry to find the correct project path and work there.
"""

            result, success = await execute_claude(prompt)

            if success:
                await send_long_message(update, result)
            else:
                await update.message.reply_text(f"❌ {result}")

            # Keep image for context (don't delete immediately)
            # photo_path.unlink(missing_ok=True)

        except Exception as e:
            logger.error(f"Photo processing error: {e}")
            await update.message.reply_text(
                f"{BOT_EMOJI} Image processing failed: {str(e)[:100]}"
            )
        return

    # Handle documents
    if update.message.document:
        filename = update.message.document.file_name or "file"
        file_size = update.message.document.file_size or 0

        # Size limit (10MB)
        if file_size > 10 * 1024 * 1024:
            await update.message.reply_text(
                f"{BOT_EMOJI} File too large ({file_size // 1024 // 1024}MB). Max 10MB."
            )
            return

        await update.message.reply_text(f"{BOT_EMOJI} 📄 Processing {filename}...")
        try:
            doc_file = await context.bot.get_file(update.message.document.file_id)
            doc_path = BASE_DIR / "temp" / filename
            doc_path.parent.mkdir(exist_ok=True)
            await doc_file.download_to_drive(doc_path)

            prompt = f"Richard sent me a file: {filename}\nSaved at: {doc_path}\n\n"
            if caption:
                prompt += f"His message: \"{caption}\"\n\n"
            prompt += "Please read this file and help him with whatever he needs."

            result, success = await execute_claude(prompt)

            if success:
                await send_long_message(update, result)
            else:
                await update.message.reply_text(f"❌ {result}")

        except Exception as e:
            logger.error(f"Document processing error: {e}")
            await update.message.reply_text(
                f"{BOT_EMOJI} File processing failed: {str(e)[:100]}"
            )
        return

    # Fallback for other media types
    await update.message.reply_text(
        f"{BOT_EMOJI} I received media but can't process this type yet. Please describe what you need!"
    )


# ============================================
# ERROR HANDLER
# ============================================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors."""
    logger.error(f"Update {update} caused error {context.error}")


# ============================================
# STARTUP
# ============================================

async def post_init(application: Application) -> None:
    """Run after bot initialization."""
    global bot_start_time
    bot_start_time = datetime.now(pytz.timezone(TIMEZONE))

    # Load session context
    context = load_session_context()
    logger.info("Session context loaded")

    # Startup notification disabled - too noisy
    # await send_to_richard(application.bot, f"{BOT_EMOJI} {BOT_NAME} is online")

    # Send callback for background tasks
    async def send_callback(text):
        await send_to_richard(application.bot, text)

    # Register all background tasks with the supervisor (auto-restart on crash)
    task_supervisor.add("heartbeat", start_heartbeat_scheduler, args=(send_callback,))
    task_supervisor.add("learning", start_learning_loop, args=(send_callback,))
    task_supervisor.add("reminders", start_reminder_scheduler, args=(send_callback,))
    task_supervisor.add("monitoring", start_monitoring_loop, args=(send_callback,))
    task_supervisor.add("health", start_health_monitor, args=(send_callback,))

    # Start all supervised background tasks
    await task_supervisor.start_all()

    # Initialize plugin system
    initialize_plugin_system(execute_claude, send_callback)
    plugin_results = await load_all_plugins()
    logger.info(f"Loaded plugins: {list(plugin_results.keys())}")


async def post_shutdown(application: Application) -> None:
    """Gracefully stop all supervised background tasks on shutdown."""
    logger.info("Shutting down supervised tasks...")
    await task_supervisor.stop_all()
    logger.info("Graceful shutdown complete")


# ============================================
# MAIN
# ============================================

def main() -> None:
    """Start the bot."""
    logger.info(f"Starting {BOT_NAME}...")

    # Build application
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Add handlers
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("status", cmd_status))
    application.add_handler(CommandHandler("history", cmd_history))
    application.add_handler(CommandHandler("heartbeat", cmd_heartbeat))
    application.add_handler(CommandHandler("memory", cmd_memory))
    application.add_handler(CommandHandler("cancel", cmd_cancel))
    application.add_handler(CommandHandler("savememory", cmd_savememory))
    application.add_handler(CommandHandler("viewhistory", cmd_viewhistory))
    application.add_handler(CommandHandler("clearhistory", cmd_clearhistory))

    # Sub-agent handlers
    application.add_handler(CommandHandler("spawn", cmd_spawn))
    application.add_handler(CommandHandler("agents", cmd_agents))
    application.add_handler(CommandHandler("agentstatus", cmd_agentstatus))
    application.add_handler(CommandHandler("cancelagent", cmd_cancelagent))

    # Learning handler
    application.add_handler(CommandHandler("learn", cmd_learn))

    # Reminder handlers
    application.add_handler(CommandHandler("remind", cmd_remind))
    application.add_handler(CommandHandler("reminders", cmd_reminders))
    application.add_handler(CommandHandler("cancelremind", cmd_cancelremind))

    # Web tools handlers
    application.add_handler(CommandHandler("weather", cmd_weather))
    application.add_handler(CommandHandler("search", cmd_search))
    application.add_handler(CommandHandler("fetch", cmd_fetch))
    application.add_handler(CommandHandler("skills", cmd_skills))
    application.add_handler(CommandHandler("dailytext", cmd_dailytext))
    application.add_handler(CommandHandler("factory", cmd_factory))

    # Project quick commands
    application.add_handler(CommandHandler("deploy", cmd_deploy))
    application.add_handler(CommandHandler("logs", cmd_logs))
    application.add_handler(CommandHandler("rollback", cmd_rollback))
    application.add_handler(CommandHandler("projects", cmd_projects))
    application.add_handler(CommandHandler("check", cmd_check))
    application.add_handler(CommandHandler("gitstatus", cmd_gitstatus))

    # Swarm commands
    application.add_handler(CommandHandler("swarm", cmd_swarm))
    application.add_handler(CommandHandler("swarms", cmd_swarms))

    # Self-update commands
    application.add_handler(CommandHandler("updateself", cmd_update_self))
    application.add_handler(CommandHandler("restart", cmd_restart))
    application.add_handler(CommandHandler("backups", cmd_backups))
    application.add_handler(CommandHandler("updatehistory", cmd_update_history))

    # Escalation commands
    application.add_handler(CommandHandler("escalations", cmd_escalations))

    # Preferences commands
    application.add_handler(CommandHandler("preferences", cmd_preferences))

    # Cost tracking commands
    application.add_handler(CommandHandler("costs", cmd_costs))
    application.add_handler(CommandHandler("budget", cmd_budget))

    # Session commands
    application.add_handler(CommandHandler("session", cmd_session))
    application.add_handler(CommandHandler("mcps", cmd_mcps))

    # Plugin commands
    application.add_handler(CommandHandler("plugins", cmd_plugins))
    application.add_handler(CommandHandler("reloadplugin", cmd_reload_plugin))
    application.add_handler(CommandHandler("skillslist", cmd_skillslist))
    application.add_handler(CommandHandler("health", cmd_health))

    # Computer use commands
    application.add_handler(CommandHandler("computer", cmd_computer))
    application.add_handler(CommandHandler("browse", cmd_browse))
    application.add_handler(CommandHandler("email", cmd_email))
    application.add_handler(CommandHandler("screenshot", cmd_screenshot))
    application.add_handler(CommandHandler("openapp", cmd_openapp))

    # Callback query handler for inline keyboards
    application.add_handler(CallbackQueryHandler(handle_callback_query))

    # Message handler for text
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message
    ))

    # Handler for photos/media - acknowledge but explain limitation
    application.add_handler(MessageHandler(
        filters.PHOTO | filters.VIDEO | filters.VOICE | filters.Document.ALL,
        handle_media
    ))

    # Error handler
    application.add_error_handler(error_handler)

    # Run the bot
    logger.info(f"{BOT_NAME} is running!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
