"""
Kiyomi Quick Actions - Telegram inline keyboards and quick responses

Features:
- Inline keyboard buttons for common actions
- Quick response templates
- Smart action suggestions based on context
"""
import logging
from typing import Optional, List, Dict, Any, Callable
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


# ============================================
# INLINE KEYBOARD BUILDERS
# ============================================

def build_confirm_keyboard(action: str, data_yes: str, data_no: str = "cancel") -> InlineKeyboardMarkup:
    """Build a Yes/No confirmation keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes", callback_data=data_yes),
            InlineKeyboardButton("❌ No", callback_data=data_no),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def build_deploy_keyboard(project_id: str) -> InlineKeyboardMarkup:
    """Build deployment action keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("🚀 Deploy", callback_data=f"deploy:{project_id}"),
            InlineKeyboardButton("📋 Logs", callback_data=f"logs:{project_id}"),
        ],
        [
            InlineKeyboardButton("⏪ Rollback", callback_data=f"rollback:{project_id}"),
            InlineKeyboardButton("🔍 Check", callback_data=f"check:{project_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def build_error_keyboard(project_id: Optional[str] = None) -> InlineKeyboardMarkup:
    """Build keyboard for error handling options."""
    buttons = [
        [
            InlineKeyboardButton("🔧 Auto-Fix", callback_data=f"autofix:{project_id or 'current'}"),
            InlineKeyboardButton("📋 Details", callback_data="error_details"),
        ],
        [
            InlineKeyboardButton("⏪ Rollback", callback_data=f"rollback:{project_id or 'current'}"),
            InlineKeyboardButton("🚫 Ignore", callback_data="ignore"),
        ]
    ]
    return InlineKeyboardMarkup(buttons)


def build_continue_keyboard() -> InlineKeyboardMarkup:
    """Build keyboard for continuing interrupted work."""
    keyboard = [
        [
            InlineKeyboardButton("▶️ Continue", callback_data="continue"),
            InlineKeyboardButton("🔄 Start Fresh", callback_data="fresh"),
        ],
        [
            InlineKeyboardButton("📋 Summary", callback_data="session_summary"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def build_project_keyboard(projects: List[Dict]) -> InlineKeyboardMarkup:
    """Build keyboard for project selection."""
    buttons = []
    row = []
    for i, project in enumerate(projects[:8]):  # Max 8 projects
        name = project.get("name", "Unknown")[:10]
        project_id = project.get("id", name.lower().replace(" ", "-"))
        row.append(InlineKeyboardButton(name, callback_data=f"project:{project_id}"))
        if len(row) == 2:  # 2 per row
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def build_quick_actions_keyboard() -> InlineKeyboardMarkup:
    """Build keyboard with common quick actions."""
    keyboard = [
        [
            InlineKeyboardButton("📊 Status", callback_data="status"),
            InlineKeyboardButton("💰 Costs", callback_data="costs"),
        ],
        [
            InlineKeyboardButton("🔍 Check Sites", callback_data="check_all"),
            InlineKeyboardButton("📝 Session", callback_data="session_summary"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def build_clarification_keyboard(options: List[str]) -> InlineKeyboardMarkup:
    """Build keyboard for clarification options."""
    buttons = []
    for i, option in enumerate(options[:4]):  # Max 4 options
        buttons.append([InlineKeyboardButton(option, callback_data=f"clarify:{i}")])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
    return InlineKeyboardMarkup(buttons)


# ============================================
# CALLBACK QUERY HANDLERS
# ============================================

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard button presses."""
    query = update.callback_query
    await query.answer()  # Acknowledge the callback

    data = query.data
    chat_id = query.message.chat_id

    # Parse the callback data
    if ":" in data:
        action, param = data.split(":", 1)
    else:
        action = data
        param = None

    # Route to appropriate handler
    handlers = {
        "deploy": _handle_deploy,
        "logs": _handle_logs,
        "rollback": _handle_rollback,
        "check": _handle_check,
        "autofix": _handle_autofix,
        "continue": _handle_continue,
        "fresh": _handle_fresh,
        "session_summary": _handle_session_summary,
        "status": _handle_status,
        "costs": _handle_costs,
        "check_all": _handle_check_all,
        "project": _handle_project_select,
        "cancel": _handle_cancel,
        "ignore": _handle_ignore,
        "error_details": _handle_error_details,
        "clarify": _handle_clarify,
    }

    handler = handlers.get(action)
    if handler:
        await handler(query, context, param)
    else:
        await query.edit_message_text(f"Unknown action: {action}")


async def _handle_deploy(query, context, project_id: str) -> None:
    """Handle deploy button press."""
    from projects import get_project
    from deploy_tools import smart_deploy

    await query.edit_message_text(f"🚀 Deploying {project_id}...")

    project = get_project(project_id)
    if not project:
        await query.edit_message_text(f"❌ Project not found: {project_id}")
        return

    async def send_update(msg):
        try:
            await query.edit_message_text(f"🚀 {msg}")
        except:
            pass

    result = await smart_deploy(project, send_update)

    if result.success:
        await query.edit_message_text(
            f"✅ **Deployed!**\n\n"
            f"**Project:** {project.name}\n"
            f"**URL:** {result.url}\n"
            f"**Verified:** {'Yes' if result.verified else 'No'}"
        )
    else:
        await query.edit_message_text(f"❌ Deploy failed: {result.message}")


async def _handle_logs(query, context, project_id: str) -> None:
    """Handle logs button press."""
    from projects import get_project
    from deploy_tools import get_vercel_logs

    project = get_project(project_id)
    if not project:
        await query.edit_message_text(f"❌ Project not found: {project_id}")
        return

    await query.edit_message_text(f"📋 Getting logs for {project.name}...")

    success, logs = await get_vercel_logs(project)

    if success:
        logs_truncated = logs[:1500] if len(logs) > 1500 else logs
        await query.edit_message_text(f"**{project.name} Logs:**\n```\n{logs_truncated}\n```")
    else:
        await query.edit_message_text(f"❌ {logs}")


async def _handle_rollback(query, context, project_id: str) -> None:
    """Handle rollback button press."""
    from projects import get_project
    from deploy_tools import rollback_vercel

    project = get_project(project_id)
    if not project:
        await query.edit_message_text(f"❌ Project not found: {project_id}")
        return

    await query.edit_message_text(f"⏪ Rolling back {project.name}...")

    async def send_update(msg):
        try:
            await query.edit_message_text(f"⏪ {msg}")
        except:
            pass

    success, message = await rollback_vercel(project, send_update)

    if success:
        await query.edit_message_text(f"✅ {message}")
    else:
        await query.edit_message_text(f"❌ {message}")


async def _handle_check(query, context, project_id: str) -> None:
    """Handle check button press."""
    from projects import get_project
    from monitoring import quick_check

    project = get_project(project_id)
    if not project or not project.url:
        await query.edit_message_text(f"❌ Project not found or has no URL")
        return

    await query.edit_message_text(f"🔍 Checking {project.name}...")

    result = await quick_check(project.url)
    await query.edit_message_text(f"**{project.name}:** {result}")


async def _handle_autofix(query, context, project_id: str) -> None:
    """Handle auto-fix button press."""
    await query.edit_message_text("🔧 Attempting auto-fix...")
    # This would trigger the escalation auto-fix
    from escalation import handle_error
    # Implementation depends on stored error context


async def _handle_continue(query, context, param: Optional[str]) -> None:
    """Handle continue button press."""
    from session_manager import get_continue_prompt, get_continuation_context
    from executor import execute_claude

    await query.edit_message_text("▶️ Resuming previous task...")

    prompt = get_continue_prompt()
    if prompt:
        result, success = await execute_claude(prompt)
        # Send result as new message
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=result[:4000]
        )
    else:
        await query.edit_message_text("No previous task to continue.")


async def _handle_fresh(query, context, param: Optional[str]) -> None:
    """Handle start fresh button press."""
    from session_manager import end_session
    end_session()
    await query.edit_message_text("🔄 Starting fresh. What would you like to do?")


async def _handle_session_summary(query, context, param: Optional[str]) -> None:
    """Handle session summary button press."""
    from session_manager import get_session_summary
    summary = get_session_summary()
    if summary:
        await query.edit_message_text(summary)
    else:
        await query.edit_message_text("No active session.")


async def _handle_status(query, context, param: Optional[str]) -> None:
    """Handle status button press."""
    from datetime import datetime
    import pytz
    from config import TIMEZONE

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    status = f"🌸 **Kiyomi Status**\n\n"
    status += f"🟢 Online\n"
    status += f"🕐 {now.strftime('%H:%M %Z')}\n"

    await query.edit_message_text(status)


async def _handle_costs(query, context, param: Optional[str]) -> None:
    """Handle costs button press."""
    from cost_tracking import generate_cost_report
    report = generate_cost_report()
    await query.edit_message_text(report[:4000])


async def _handle_check_all(query, context, param: Optional[str]) -> None:
    """Handle check all sites button press."""
    from monitoring import generate_status_report
    await query.edit_message_text("🔍 Checking all sites...")
    report = generate_status_report()
    await query.edit_message_text(report)


async def _handle_project_select(query, context, project_id: str) -> None:
    """Handle project selection."""
    from projects import get_project
    project = get_project(project_id)
    if project:
        # Show project actions
        keyboard = build_deploy_keyboard(project_id)
        await query.edit_message_text(
            f"**{project.name}**\n"
            f"Path: `{project.path}`\n"
            f"URL: {project.url or 'N/A'}",
            reply_markup=keyboard
        )
    else:
        await query.edit_message_text(f"❌ Project not found: {project_id}")


async def _handle_cancel(query, context, param: Optional[str]) -> None:
    """Handle cancel button press."""
    await query.edit_message_text("Cancelled.")


async def _handle_ignore(query, context, param: Optional[str]) -> None:
    """Handle ignore button press."""
    await query.edit_message_text("Ignored.")


async def _handle_error_details(query, context, param: Optional[str]) -> None:
    """Handle error details button press."""
    from escalation import get_recent_escalations
    recent = get_recent_escalations(1)
    if recent:
        e = recent[0]
        await query.edit_message_text(
            f"**Error Details**\n\n"
            f"Type: {e['type']}\n"
            f"Title: {e['title']}\n"
            f"Project: {e.get('project', 'N/A')}"
        )
    else:
        await query.edit_message_text("No recent errors.")


async def _handle_clarify(query, context, option_index: str) -> None:
    """Handle clarification option selection."""
    # This would need context about what options were presented
    await query.edit_message_text(f"Selected option {option_index}")


# ============================================
# SMART ACTION SUGGESTIONS
# ============================================

def suggest_actions_for_context(
    project: Optional[str] = None,
    last_action: Optional[str] = None,
    has_error: bool = False
) -> Optional[InlineKeyboardMarkup]:
    """
    Suggest relevant actions based on current context.
    Returns an inline keyboard or None.
    """
    if has_error:
        return build_error_keyboard(project)

    if project:
        return build_deploy_keyboard(project)

    return None


def suggest_actions_for_message(message: str) -> Optional[InlineKeyboardMarkup]:
    """
    Analyze a message and suggest relevant quick actions.
    """
    message_lower = message.lower()

    # Deployment-related
    if any(w in message_lower for w in ["deploy", "push", "ship"]):
        from projects import list_projects
        projects = [{"name": p.name, "id": p.name.lower().replace(" ", "-")}
                   for p in list_projects()]
        if projects:
            return build_project_keyboard(projects)

    # Error-related
    if any(w in message_lower for w in ["error", "bug", "broken", "fix"]):
        return build_error_keyboard()

    return None
