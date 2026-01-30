"""
Git Helper Plugin

Quick git operations for all projects.
"""
from plugin_system import KiyomiPlugin

PLUGIN_INFO = {
    'name': 'Git Helper',
    'version': '1.0.0',
    'description': 'Quick git operations across projects',
    'author': 'Richard',
    'commands': ['gs', 'gc', 'gp', 'gitall'],
    'triggers': [
        r'^commit\s+(.+)$',           # "commit message here"
        r'^push\s+(changes|code)$',   # "push changes"
    ],
}


class Plugin(KiyomiPlugin):
    """Git helper plugin."""

    def __init__(self, api):
        super().__init__(api)
        self.name = "Git Helper"

    async def on_load(self) -> bool:
        return True

    async def on_unload(self) -> bool:
        return True

    async def on_command(self, command: str, args: list, context: dict) -> str:
        """Handle git commands."""

        if command == "gs":
            # Git status for current or specified project
            return await self._git_status(args[0] if args else None)

        if command == "gc":
            # Git commit
            if not args:
                return "Usage: `/gc <commit message>`"
            message = " ".join(args)
            return await self._git_commit(message)

        if command == "gp":
            # Git push
            return await self._git_push(args[0] if args else None)

        if command == "gitall":
            # Status of all projects
            return await self._git_all_status()

        return None

    async def on_trigger(self, trigger: str, match: str, context: dict) -> str:
        """Handle git triggers."""
        import re

        # Commit trigger
        m = re.match(r'^commit\s+(.+)$', match, re.IGNORECASE)
        if m:
            message = m.group(1)
            return await self._git_commit(message)

        # Push trigger
        if re.match(r'^push\s+(changes|code)$', match, re.IGNORECASE):
            return await self._git_push(None)

        return None

    async def _git_status(self, project_name: str = None) -> str:
        """Get git status."""
        if project_name:
            project = self.api.get_project(project_name)
            if not project:
                return f"❌ Project not found: {project_name}"
            path = project.path
            name = project.name
        else:
            session = self.api.get_session()
            if session and session.current_project:
                project = self.api.get_project(session.current_project)
                if project:
                    path = project.path
                    name = project.name
                else:
                    return "No current project. Use `/gs <project>`"
            else:
                return "No current project. Use `/gs <project>`"

        result, success = await self.api.execute(
            f"Run `git status` in {path} and summarize the changes."
        )

        return f"**Git Status - {name}**\n\n{result[:1000]}"

    async def _git_commit(self, message: str) -> str:
        """Commit changes."""
        session = self.api.get_session()
        if not session or not session.current_project:
            return "No current project. Work on a project first."

        project = self.api.get_project(session.current_project)
        if not project:
            return "Current project not found."

        result, success = await self.api.execute(
            f"In {project.path}:\n"
            f"1. Run `git add -A`\n"
            f"2. Run `git commit -m \"{message}\"`\n"
            f"Report what was committed."
        )

        if success:
            return f"✅ **Committed to {project.name}**\n\n{result[:500]}"
        else:
            return f"❌ Commit failed: {result[:300]}"

    async def _git_push(self, project_name: str = None) -> str:
        """Push changes."""
        if project_name:
            project = self.api.get_project(project_name)
        else:
            session = self.api.get_session()
            if session and session.current_project:
                project = self.api.get_project(session.current_project)
            else:
                return "No current project. Use `/gp <project>`"

        if not project:
            return "Project not found."

        result, success = await self.api.execute(
            f"In {project.path}, run `git push` and report the result."
        )

        if success:
            return f"✅ **Pushed {project.name}**\n\n{result[:500]}"
        else:
            return f"❌ Push failed: {result[:300]}"

    async def _git_all_status(self) -> str:
        """Get status of all projects."""
        projects = self.api.list_projects()

        result, success = await self.api.execute(
            "Check git status for these projects and report which have uncommitted changes:\n" +
            "\n".join(f"- {p.name}: {p.path}" for p in projects[:10])
        )

        return f"**Git Status - All Projects**\n\n{result[:1500]}"
