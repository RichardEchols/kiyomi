"""
Kiyomi Connection Manager - Reliable network connections

Features:
- Auto-retry on connection failures
- Exponential backoff
- Connection health monitoring
- Graceful reconnection
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Callable, Any
from functools import wraps

import pytz
from config import TIMEZONE

logger = logging.getLogger(__name__)

# Connection configuration
MAX_RETRIES = 5
BASE_DELAY = 1  # seconds
MAX_DELAY = 60  # seconds
CONNECTION_TIMEOUT = 30  # seconds


class ConnectionState:
    """Track connection state."""

    def __init__(self):
        self.connected: bool = False
        self.last_success: Optional[datetime] = None
        self.last_failure: Optional[datetime] = None
        self.consecutive_failures: int = 0
        self.total_failures: int = 0
        self.total_retries: int = 0


# Global connection states
_telegram_state = ConnectionState()
_claude_state = ConnectionState()


def calculate_backoff(failures: int) -> float:
    """Calculate exponential backoff delay."""
    delay = min(BASE_DELAY * (2 ** failures), MAX_DELAY)
    return delay


def retry_with_backoff(max_retries: int = MAX_RETRIES):
    """
    Decorator for automatic retry with exponential backoff.

    Usage:
        @retry_with_backoff(max_retries=3)
        async def my_function():
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None

            for attempt in range(max_retries):
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    last_error = e
                    delay = calculate_backoff(attempt)
                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)

            # All retries exhausted
            logger.error(f"{func.__name__} failed after {max_retries} attempts")
            raise last_error

        return wrapper
    return decorator


async def with_timeout(coro, timeout: float = CONNECTION_TIMEOUT):
    """Execute a coroutine with timeout."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        raise TimeoutError(f"Operation timed out after {timeout}s")


def record_success(state: ConnectionState) -> None:
    """Record a successful connection."""
    tz = pytz.timezone(TIMEZONE)
    state.connected = True
    state.last_success = datetime.now(tz)
    state.consecutive_failures = 0


def record_failure(state: ConnectionState, error: Optional[Exception] = None) -> None:
    """Record a connection failure."""
    tz = pytz.timezone(TIMEZONE)
    state.last_failure = datetime.now(tz)
    state.consecutive_failures += 1
    state.total_failures += 1

    if state.consecutive_failures >= 3:
        state.connected = False


def get_telegram_state() -> ConnectionState:
    """Get Telegram connection state."""
    return _telegram_state


def get_claude_state() -> ConnectionState:
    """Get Claude connection state."""
    return _claude_state


def get_connection_status() -> dict:
    """Get overall connection status."""
    return {
        "telegram": {
            "connected": _telegram_state.connected,
            "consecutive_failures": _telegram_state.consecutive_failures,
            "last_success": _telegram_state.last_success.isoformat() if _telegram_state.last_success else None,
        },
        "claude": {
            "connected": _claude_state.connected,
            "consecutive_failures": _claude_state.consecutive_failures,
            "last_success": _claude_state.last_success.isoformat() if _claude_state.last_success else None,
        }
    }


class ReconnectingClient:
    """
    Base class for clients that automatically reconnect.
    """

    def __init__(self, name: str):
        self.name = name
        self.state = ConnectionState()
        self._reconnect_task: Optional[asyncio.Task] = None

    async def connect(self) -> bool:
        """Override in subclass to implement connection logic."""
        raise NotImplementedError

    async def disconnect(self) -> None:
        """Override in subclass to implement disconnection logic."""
        raise NotImplementedError

    async def ensure_connected(self) -> bool:
        """Ensure the client is connected, reconnecting if necessary."""
        if self.state.connected:
            return True

        return await self._reconnect()

    async def _reconnect(self) -> bool:
        """Attempt to reconnect with backoff."""
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"{self.name}: Reconnection attempt {attempt + 1}/{MAX_RETRIES}")

                success = await with_timeout(self.connect())

                if success:
                    record_success(self.state)
                    logger.info(f"{self.name}: Reconnected successfully")
                    return True

            except Exception as e:
                record_failure(self.state, e)
                delay = calculate_backoff(attempt)
                logger.warning(f"{self.name}: Reconnection failed: {e}. Waiting {delay}s...")
                await asyncio.sleep(delay)

        logger.error(f"{self.name}: Failed to reconnect after {MAX_RETRIES} attempts")
        return False

    def start_auto_reconnect(self) -> None:
        """Start automatic reconnection monitoring."""
        if self._reconnect_task is None or self._reconnect_task.done():
            self._reconnect_task = asyncio.create_task(self._auto_reconnect_loop())

    async def _auto_reconnect_loop(self) -> None:
        """Background loop to monitor and reconnect."""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds

                if not self.state.connected:
                    await self._reconnect()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"{self.name}: Auto-reconnect error: {e}")


# Utility functions for common patterns

async def safe_send(send_fn: Callable, message: str, max_retries: int = 3) -> bool:
    """Safely send a message with retries."""
    for attempt in range(max_retries):
        try:
            await send_fn(message)
            record_success(_telegram_state)
            return True
        except Exception as e:
            record_failure(_telegram_state, e)
            if attempt < max_retries - 1:
                delay = calculate_backoff(attempt)
                await asyncio.sleep(delay)

    return False


async def safe_execute(execute_fn: Callable, prompt: str, max_retries: int = 2) -> tuple:
    """Safely execute a Claude command with retries."""
    for attempt in range(max_retries):
        try:
            result, success = await execute_fn(prompt)
            if success:
                record_success(_claude_state)
            return result, success
        except Exception as e:
            record_failure(_claude_state, e)
            if attempt < max_retries - 1:
                delay = calculate_backoff(attempt)
                logger.warning(f"Claude execution failed, retrying in {delay}s: {e}")
                await asyncio.sleep(delay)

    return "Execution failed after retries", False
