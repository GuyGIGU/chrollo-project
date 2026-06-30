"""The cross-process cache lock (fix ④): re-entrant within a process, exclusive
across processes. The cross-process half is what the in-process SCAN_LOCK could
not provide — a CLI ``run_screener.py`` and the scheduler subprocess writing the
same parquet/meta must not interleave."""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.pipeline.file_lock import cache_lock  # noqa: E402


def test_reentrant_within_process(tmp_path):
    cache = str(tmp_path / "cache.parquet")
    with cache_lock(cache, timeout=2):
        with cache_lock(cache, timeout=2):  # must not deadlock
            pass
    # fully released → re-acquirable
    with cache_lock(cache, timeout=2):
        pass


def test_excludes_a_second_process(tmp_path):
    cache = str(tmp_path / "cache.parquet")
    ready = tmp_path / "ready.flag"
    release = tmp_path / "release.flag"

    # Child grabs the lock, signals ready, then waits for the parent to free it.
    holder = textwrap.dedent(f"""
        import sys, time
        sys.path.insert(0, {str(ROOT)!r})
        from core.pipeline.file_lock import cache_lock
        with cache_lock({cache!r}, timeout=5):
            open({str(ready)!r}, 'w').close()
            for _ in range(200):
                if {str(release)!r} and __import__('os').path.exists({str(release)!r}):
                    break
                time.sleep(0.05)
    """)
    proc = subprocess.Popen([sys.executable, "-c", holder])
    try:
        for _ in range(100):
            if ready.exists():
                break
            time.sleep(0.05)
        assert ready.exists(), "child never acquired the lock"

        # While the child holds it, this process cannot acquire within the timeout.
        with pytest.raises(TimeoutError):
            with cache_lock(cache, timeout=0.5):
                pass
    finally:
        release.write_text("go")
        proc.wait(timeout=10)

    # Once the child has exited, the lock is free again.
    with cache_lock(cache, timeout=2):
        pass
