from __future__ import annotations

import asyncio
import inspect
import logging
import threading
import time
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

T = TypeVar("T")
log = logging.getLogger("scrubsync.fencer")


class StaleEpochException(RuntimeError):
    """A computation completed after its authority to commit was revoked."""


class EpochManager:
    """
    A process-local, thread-safe fencing authority.

    A task's cancellation is best-effort. The epoch comparison is authoritative.

    Async callers must run on one owning event loop. advance_epoch() may also
    be called from another thread; task cancellation is marshalled to the
    task's owning loop.

    Do not perform awaitable side effects in commit(). Enqueue synchronously,
    and recheck the epoch at the eventual external side-effect boundary.
    """

    def __init__(self, initial_epoch: int = 0) -> None:
        self._epoch = initial_epoch
        self._lock = threading.RLock()
        self._tasks: set[asyncio.Future[Any]] = set()
        self.last_advance_ns: int | None = None
        self.stale_rejections = 0

    @property
    def current_epoch(self) -> int:
        with self._lock:
            return self._epoch

    def is_current(self, epoch: int) -> bool:
        with self._lock:
            return epoch == self._epoch

    @staticmethod
    def _cancel(task: asyncio.Future[Any]) -> None:
        if task.done():
            return
        loop = task.get_loop()
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            task.cancel()
        elif not loop.is_closed():
            loop.call_soon_threadsafe(task.cancel)

    def advance_epoch(self) -> int:
        with self._lock:
            self._epoch += 1
            epoch = self._epoch
            self.last_advance_ns = time.perf_counter_ns()
            tasks = tuple(self._tasks)
        for task in tasks:
            self._cancel(task)
        log.info(
            "epoch_advanced epoch=%s timestamp_ns=%s cancelled_candidates=%s",
            epoch,
            self.last_advance_ns,
            len(tasks),
        )
        return epoch

    def assert_current(self, epoch: int) -> None:
        with self._lock:
            if epoch != self._epoch:
                self.stale_rejections += 1
                raise StaleEpochException(
                    f"Epoch {epoch} is stale; current epoch is {self._epoch}"
                )

    def commit(self, epoch: int, effect: Callable[[], T]) -> T:
        """Atomically authorize a synchronous state mutation or queue insertion."""
        with self._lock:
            self.assert_current(epoch)
            return effect()

    async def run_fenced_task(
        self, epoch: int, coro: Coroutine[Any, Any, T]
    ) -> T:
        with self._lock:
            if epoch != self._epoch:
                if inspect.iscoroutine(coro):
                    coro.close()
                self.stale_rejections += 1
                raise StaleEpochException(f"Refusing stale epoch {epoch}")
            task = asyncio.create_task(coro)
            self._tasks.add(task)

        try:
            result = await task
            self.assert_current(epoch)
            return result
        finally:
            with self._lock:
                self._tasks.discard(task)