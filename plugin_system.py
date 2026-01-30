"""
Kiyomi Plugin System - Easy extensibility with plugins

Features:
- Load plugins from a plugins directory
- Hot-reload plugins without restart
- Plugin lifecycle management
- Plugin discovery and registration
- Inter-plugin communication
"""
import asyncio
import importlib
import importlib.util
import logging
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any, Callable, Tuple
from abc import ABC, abstractmethod

import pytz
from config import BASE_DIR, TIMEZONE

logger = logging.getLogger(__name__)

# Plugin configuration
PLUGINS_DIR = BASE_DIR / "plugins"
PLUGIN_CONFIG_FILE = BASE_DIR / "plugin_config.json"
PLUGINS_DIR.mkdir(exist_ok=True)


@dataclass
class PluginInfo:
    """Information about a plugin."""
    name: str
    version: str
    description: str
    author: str
    enabled: bool = True
    commands: List[str] = field(default_factory=list)
    triggers: List[str] = field(default_factory=list)  # Regex patterns
    loaded_at: Optional[datetime] = None
    error: Optional[str] = None


class KiyomiPlugin(ABC):
    """
    Base class for Kiyomi plugins.

    To create a plugin:
    1. Create a .py file in the plugins directory
    2. Define a class that inherits from KiyomiPlugin
    3. Implement the required methods
    4. Define PLUGIN_INFO at module level
    """

    def __init__(self, kiyomi_api: 'PluginAPI'):
        self.api = kiyomi_api
        self.name = "BasePlugin"
        self.version = "1.0.0"

    @abstractmethod
    async def on_load(self) -> bool:
        """Called when plugin is loaded. Return True if successful."""
        pass

    @abstractmethod
    async def on_unload(self) -> bool:
        """Called when plugin is unloaded. Return True if successful."""
        pass

    async def on_message(self, message: str, context: Dict) -> Optional[str]:
        """
        Called for every message. Return a response to handle it,
        or None to let other handlers process it.
        """
        return None

    async def on_command(self, command: str, args: List[str], context: Dict) -> Optional[str]:
        """
        Called when a registered command is invoked.
        Return a response string.
        """
        return None

    async def on_trigger(self, trigger: str, match: str, context: Dict) -> Optional[str]:
        """
        Called when a registered trigger pattern matches.
        Return a response string.
        """
        return None


class PluginAPI:
    """
    API provided to plugins for interacting with Kiyomi.
    """

    def __init__(self, executor_fn, send_fn):
        self._execute = executor_fn
        self._send = send_fn
        self._storage: Dict[str, Dict] = {}

    async def execute(self, prompt: str) -> Tuple[str, bool]:
        """Execute a prompt via Claude."""
        return await self._execute(prompt)

    async def send_message(self, text: str) -> bool:
        """Send a message to the user."""
        try:
            await self._send(text)
            return True
        except:
            return False

    def get_storage(self, plugin_name: str) -> Dict:
        """Get persistent storage for a plugin."""
        if plugin_name not in self._storage:
            self._storage[plugin_name] = self._load_plugin_storage(plugin_name)
        return self._storage[plugin_name]

    def save_storage(self, plugin_name: str, data: Dict) -> bool:
        """Save plugin storage."""
        self._storage[plugin_name] = data
        return self._save_plugin_storage(plugin_name, data)

    def _load_plugin_storage(self, plugin_name: str) -> Dict:
        storage_file = PLUGINS_DIR / f"{plugin_name}_storage.json"
        try:
            if storage_file.exists():
                with open(storage_file) as f:
                    return json.load(f)
        except:
            pass
        return {}

    def _save_plugin_storage(self, plugin_name: str, data: Dict) -> bool:
        storage_file = PLUGINS_DIR / f"{plugin_name}_storage.json"
        try:
            with open(storage_file, "w") as f:
                json.dump(data, f, indent=2)
            return True
        except:
            return False

    def get_project(self, name: str):
        """Get a project by name."""
        from projects import get_project_by_name
        return get_project_by_name(name)

    def list_projects(self):
        """List all projects."""
        from projects import list_projects
        return list_projects()

    def get_session(self):
        """Get current session info."""
        from session_manager import get_current_session
        return get_current_session()


# Global plugin state
_plugins: Dict[str, KiyomiPlugin] = {}
_plugin_info: Dict[str, PluginInfo] = {}
_plugin_api: Optional[PluginAPI] = None


def initialize_plugin_system(executor_fn, send_fn) -> None:
    """Initialize the plugin system with required functions."""
    global _plugin_api
    _plugin_api = PluginAPI(executor_fn, send_fn)
    logger.info("Plugin system initialized")


def load_plugin(plugin_path: Path) -> Tuple[bool, str]:
    """
    Load a plugin from a file.

    Returns (success, message)
    """
    global _plugins, _plugin_info, _plugin_api

    if _plugin_api is None:
        return False, "Plugin system not initialized"

    try:
        # Load the module
        spec = importlib.util.spec_from_file_location(
            plugin_path.stem,
            plugin_path
        )
        if spec is None or spec.loader is None:
            return False, f"Could not load spec for {plugin_path}"

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Get plugin info
        if not hasattr(module, 'PLUGIN_INFO'):
            return False, "Plugin missing PLUGIN_INFO"

        info_dict = module.PLUGIN_INFO
        info = PluginInfo(
            name=info_dict.get('name', plugin_path.stem),
            version=info_dict.get('version', '1.0.0'),
            description=info_dict.get('description', ''),
            author=info_dict.get('author', 'Unknown'),
            commands=info_dict.get('commands', []),
            triggers=info_dict.get('triggers', []),
        )

        # Get plugin class
        if not hasattr(module, 'Plugin'):
            return False, "Plugin missing Plugin class"

        plugin_class = module.Plugin
        if not issubclass(plugin_class, KiyomiPlugin):
            return False, "Plugin class must inherit from KiyomiPlugin"

        # Instantiate plugin
        plugin = plugin_class(_plugin_api)

        # Call on_load
        asyncio.create_task(_async_load_plugin(plugin, info))

        return True, f"Plugin '{info.name}' loading..."

    except Exception as e:
        logger.error(f"Error loading plugin {plugin_path}: {e}")
        return False, f"Error: {e}"


async def _async_load_plugin(plugin: KiyomiPlugin, info: PluginInfo) -> None:
    """Async helper to load plugin."""
    global _plugins, _plugin_info

    try:
        success = await plugin.on_load()
        if success:
            tz = pytz.timezone(TIMEZONE)
            info.loaded_at = datetime.now(tz)
            _plugins[info.name] = plugin
            _plugin_info[info.name] = info
            logger.info(f"Plugin '{info.name}' loaded successfully")
        else:
            info.error = "on_load returned False"
            logger.warning(f"Plugin '{info.name}' failed to load")
    except Exception as e:
        info.error = str(e)
        logger.error(f"Plugin '{info.name}' error: {e}")


async def unload_plugin(name: str) -> Tuple[bool, str]:
    """Unload a plugin by name."""
    global _plugins, _plugin_info

    if name not in _plugins:
        return False, f"Plugin '{name}' not loaded"

    try:
        plugin = _plugins[name]
        success = await plugin.on_unload()

        del _plugins[name]
        if name in _plugin_info:
            del _plugin_info[name]

        if success:
            logger.info(f"Plugin '{name}' unloaded")
            return True, f"Plugin '{name}' unloaded"
        else:
            return True, f"Plugin '{name}' unloaded (with warnings)"

    except Exception as e:
        logger.error(f"Error unloading plugin {name}: {e}")
        return False, f"Error: {e}"


async def reload_plugin(name: str) -> Tuple[bool, str]:
    """Reload a plugin (unload then load)."""
    # Find the plugin file
    plugin_file = PLUGINS_DIR / f"{name}.py"
    if not plugin_file.exists():
        # Try to find by name in loaded plugins
        for pname, info in _plugin_info.items():
            if info.name == name:
                plugin_file = PLUGINS_DIR / f"{pname}.py"
                break

    if not plugin_file.exists():
        return False, f"Plugin file not found for '{name}'"

    # Unload if loaded
    if name in _plugins:
        await unload_plugin(name)

    # Load
    return load_plugin(plugin_file)


def discover_plugins() -> List[Path]:
    """Discover all plugin files in the plugins directory."""
    return list(PLUGINS_DIR.glob("*.py"))


async def load_all_plugins() -> Dict[str, str]:
    """Load all discovered plugins. Returns dict of name -> status."""
    results = {}

    for plugin_path in discover_plugins():
        if plugin_path.name.startswith("_"):
            continue  # Skip private files

        success, message = load_plugin(plugin_path)
        results[plugin_path.stem] = message

    return results


def get_loaded_plugins() -> List[PluginInfo]:
    """Get list of loaded plugins."""
    return list(_plugin_info.values())


def get_plugin(name: str) -> Optional[KiyomiPlugin]:
    """Get a loaded plugin by name."""
    return _plugins.get(name)


async def dispatch_message(message: str, context: Dict) -> Optional[str]:
    """
    Dispatch a message to all plugins.
    Returns the first non-None response.
    """
    for name, plugin in _plugins.items():
        try:
            response = await plugin.on_message(message, context)
            if response is not None:
                return response
        except Exception as e:
            logger.error(f"Plugin {name} error in on_message: {e}")

    return None


async def dispatch_command(command: str, args: List[str], context: Dict) -> Optional[str]:
    """
    Dispatch a command to the appropriate plugin.
    """
    for name, info in _plugin_info.items():
        if command in info.commands:
            plugin = _plugins.get(name)
            if plugin:
                try:
                    return await plugin.on_command(command, args, context)
                except Exception as e:
                    logger.error(f"Plugin {name} error in on_command: {e}")
                    return f"Plugin error: {e}"

    return None


async def dispatch_trigger(message: str, context: Dict) -> Optional[str]:
    """
    Check all plugin triggers against a message.
    Returns the first matching response.
    """
    import re

    for name, info in _plugin_info.items():
        for trigger in info.triggers:
            match = re.search(trigger, message, re.IGNORECASE)
            if match:
                plugin = _plugins.get(name)
                if plugin:
                    try:
                        response = await plugin.on_trigger(trigger, match.group(), context)
                        if response:
                            return response
                    except Exception as e:
                        logger.error(f"Plugin {name} error in on_trigger: {e}")

    return None


def format_plugin_list() -> str:
    """Format loaded plugins for display."""
    plugins = get_loaded_plugins()

    if not plugins:
        return "No plugins loaded.\n\nAdd plugins to: " + str(PLUGINS_DIR)

    msg = "**Loaded Plugins:**\n\n"
    for p in plugins:
        status = "✅" if p.error is None else "❌"
        msg += f"{status} **{p.name}** v{p.version}\n"
        msg += f"   {p.description}\n"
        if p.commands:
            msg += f"   Commands: {', '.join(p.commands)}\n"
        if p.error:
            msg += f"   Error: {p.error}\n"
        msg += "\n"

    return msg
