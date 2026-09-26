"""Cross-process advisory lock for the per-universe market-data cache.

The scheduler (in-process), manual SSE jobs, and a standalone CLI ``run_screener.py``
are SEPARATE processes that each read-modify-write the same per-universe parquet +
``cache_meta`` json. The in-process ``threading.Lock`` (``SCAN_LOCK`` in the webapp)
does not span processes, so two overlapping fetchers could interleave and clobber the
cache or leave a torn parquet/meta pair. This module serializes the whole
read-fetch-write window across processes by an OS advisory lock keyed on the cache
path.

It is **re-entrant within a process** (the download-only path holds the lock and then
calls ``fetch_data``, which re-acquires the same path — that must not deadlock) and
**exclusive across processes** (``msvcrt`` on Windows, ``fcntl`` elsewhere). The OS
releases the lock when the fd closes or the process dies, so a crash cannot strand it.
"""
from __future__ import annotations

import contextlib
import os
import threading
import time

# abspath(lockfile) -> [holds, fd]; guarded by _GUARD for the in-process bookkeeping.
_HELD: dict[str, list] = {}
_GUARD = threading.Lock()


if os.name == "nt":
    import msvcrt

    def _try_lock(handle) -> bool:
        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False

    def _unlock(handle) -> None:
        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
else:
    import fcntl

    def _try_lock(handle) -> bool:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def _unlock(handle) -> None:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass


@contextlib.contextmanager
def cache_lock(cache_path: str, *, timeout: float = 1800.0, poll: float = 0.5):
    """Hold an exclusive cross-process lock for ``cache_path``'s read-write window.

    Re-entrant per process. Across processes, polls for the OS lock up to ``timeout``
    seconds; raises ``TimeoutError`` rather than proceeding unlocked (a stuck holder
    is surfaced, never silently raced). ``timeout`` is generous because a legitimate
    holder may be a multi-minute cold refetch.
    """
    lock_path = os.path.abspath(cache_path) + ".lock"

    with _GUARD:
        entry = _HELD.get(lock_path)
        if entry is not None:
            entry[0] += 1
            reentered = True
        else:
            reentered = False

    if reentered:
        try:
            yield
        finally:
            _decref(lock_path)
        return

    handle = open(lock_path, "a+")
    acquired = False
    deadline = time.monotonic() + max(0.0, timeout)
    try:
        while True:
            if _try_lock(handle):
                acquired = True
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"could not acquire market-data cache lock {lock_path} within "
                    f"{timeout:.0f}s; another scan/download is holding it"
                )
            time.sleep(poll)
        with _GUARD:
            _HELD[lock_path] = [1, handle]
    except BaseException:
        if not acquired:
            handle.close()
        raise

    try:
        yield
    finally:
        _decref(lock_path)


def _decref(lock_path: str) -> None:
    with _GUARD:
        entry = _HELD.get(lock_path)
        if entry is None:
            return
        entry[0] -= 1
        if entry[0] > 0:
            return
        del _HELD[lock_path]
    _unlock(entry[1])
    entry[1].close()
