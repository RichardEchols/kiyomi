"""
Supervisor - Background task management with auto-restart on crash.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class SupervisedTask:
    def __init__(self, name, coro_factory, args=(), max_restarts=50, base_delay=5.0, max_delay=300.0):
        self.name = name
        self._coro_factory = coro_factory
        self._args = args
        self._max_restarts = max_restarts
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._task = None
        self._restarts = 0
        self._running = False
        self._started_at = None
        self._last_crash = None
        self._last_error = ''

    @property
    def status(self):
        return {
            'name': self.name,
            'running': self._running,
            'restarts': self._restarts,
            'last_error': self._last_error,
        }

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._supervise())
        logger.info(f'[supervisor] Started: {self.name}')

    async def stop(self):
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info(f'[supervisor] Stopped: {self.name}')

    async def _supervise(self):
        delay = self._base_delay
        while self._running and self._restarts < self._max_restarts:
            self._started_at = datetime.now()
            try:
                await self._coro_factory(*self._args)
                break
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._restarts += 1
                self._last_crash = datetime.now()
                self._last_error = str(e)[:200]
                logger.error(f'[supervisor] {self.name} crashed (restart {self._restarts}/{self._max_restarts}): {e}')
                if not self._running:
                    break
                await asyncio.sleep(delay)
                delay = min(delay * 2, self._max_delay)
                if self._started_at and (datetime.now() - self._started_at).total_seconds() > 300:
                    delay = self._base_delay
        if self._restarts >= self._max_restarts:
            logger.critical(f'[supervisor] {self.name} exceeded max restarts!')


class Supervisor:
    def __init__(self):
        self._tasks = {}

    def add(self, name, coro_factory, args=(), **kwargs):
        self._tasks[name] = SupervisedTask(name, coro_factory, args, **kwargs)

    async def start_all(self):
        for task in self._tasks.values():
            await task.start()
        logger.info(f'[supervisor] All {len(self._tasks)} tasks started')

    async def stop_all(self):
        await asyncio.gather(*(t.stop() for t in self._tasks.values()), return_exceptions=True)
        logger.info('[supervisor] All tasks stopped')

    def status(self):
        return [t.status for t in self._tasks.values()]
