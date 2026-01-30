"""
Example Kiyomi Plugin

This demonstrates how to create a plugin for Kiyomi.
"""
from plugin_system import KiyomiPlugin

# Plugin metadata - REQUIRED
PLUGIN_INFO = {
    'name': 'Example Plugin',
    'version': '1.0.0',
    'description': 'An example plugin showing the plugin structure',
    'author': 'Richard',
    'commands': ['example', 'ping'],  # Commands this plugin handles
    'triggers': [r'hello\s+kiyomi'],   # Regex patterns to trigger on
}


class Plugin(KiyomiPlugin):
    """
    Example plugin implementation.

    The class MUST be named 'Plugin' and inherit from KiyomiPlugin.
    """

    def __init__(self, api):
        super().__init__(api)
        self.name = "Example Plugin"
        self.counter = 0

    async def on_load(self) -> bool:
        """Called when plugin loads."""
        # Load any saved state
        storage = self.api.get_storage("example")
        self.counter = storage.get("counter", 0)
        return True

    async def on_unload(self) -> bool:
        """Called when plugin unloads."""
        # Save state
        self.api.save_storage("example", {"counter": self.counter})
        return True

    async def on_command(self, command: str, args: list, context: dict) -> str:
        """Handle registered commands."""
        if command == "example":
            self.counter += 1
            return f"Example plugin called {self.counter} times!"

        if command == "ping":
            return "Pong! 🏓"

        return None

    async def on_trigger(self, trigger: str, match: str, context: dict) -> str:
        """Handle trigger pattern matches."""
        if "hello" in match.lower():
            return "Hello! I'm an example plugin. 👋"
        return None

    async def on_message(self, message: str, context: dict) -> str:
        """
        Called for every message.
        Return None to let other handlers process it.
        """
        # Example: respond to specific phrase
        if message.lower() == "what plugins are loaded":
            plugins = ["Example Plugin"]  # In real use, query the system
            return f"Loaded plugins: {', '.join(plugins)}"

        return None  # Let other handlers process
