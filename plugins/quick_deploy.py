"""
Quick Deploy Plugin

Provides ultra-fast deployment shortcuts.
"""
from plugin_system import KiyomiPlugin

PLUGIN_INFO = {
    'name': 'Quick Deploy',
    'version': '1.0.0',
    'description': 'Fast deployment shortcuts for common projects',
    'author': 'Richard',
    'commands': ['qd', 'quickdeploy'],
    'triggers': [
        r'^deploy\s+(\w+)$',      # "deploy projectname"
        r'^ship\s+(\w+)$',         # "ship projectname"
        r'^push\s+(\w+)\s+live$',  # "push projectname live"
    ],
}


class Plugin(KiyomiPlugin):
    """Quick deployment plugin."""

    def __init__(self, api):
        super().__init__(api)
        self.name = "Quick Deploy"

    async def on_load(self) -> bool:
        return True

    async def on_unload(self) -> bool:
        return True

    async def on_command(self, command: str, args: list, context: dict) -> str:
        """Handle qd/quickdeploy command."""
        if not args:
            # List deployable projects
            projects = self.api.list_projects()
            names = [p.name for p in projects if p.deploy_cmd]
            return f"**Quick Deploy**\n\nUsage: `/qd <project>`\n\nProjects: {', '.join(names)}"

        project_name = " ".join(args)
        return await self._deploy(project_name)

    async def on_trigger(self, trigger: str, match: str, context: dict) -> str:
        """Handle deploy triggers."""
        import re

        # Extract project name from match
        patterns = [
            r'^(?:deploy|ship)\s+(\w+)',
            r'^push\s+(\w+)\s+live',
        ]

        for pattern in patterns:
            m = re.match(pattern, match, re.IGNORECASE)
            if m:
                project_name = m.group(1)
                return await self._deploy(project_name)

        return None

    async def _deploy(self, project_name: str) -> str:
        """Deploy a project."""
        project = self.api.get_project(project_name)

        if not project:
            return f"❌ Project not found: {project_name}"

        if not project.deploy_cmd:
            return f"❌ No deploy command for {project.name}"

        # Execute deployment
        result, success = await self.api.execute(
            f"Deploy {project.name} using: {project.deploy_cmd}\n"
            f"Working directory: {project.path}\n"
            f"After deploy, verify the site is up at {project.url}"
        )

        if success:
            return f"✅ **{project.name} Deployed**\n\n{result[:500]}"
        else:
            return f"❌ Deploy failed: {result[:300]}"
