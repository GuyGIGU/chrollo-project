import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

from domains.archive.episode_cache import VersionedCache


def _counter():
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return f"value-{calls['n']}"

    return calls, compute


def test_miss_computes_then_hit_reuses():
    cache = VersionedCache()
    calls, compute = _counter()
    assert cache.get_or_compute("k", version=1, compute=compute) == "value-1"
    assert cache.get_or_compute("k", version=1, compute=compute) == "value-1"
    assert calls["n"] == 1   # second call served from cache, no recompute


def test_version_change_recomputes():
    cache = VersionedCache()
    calls, compute = _counter()
    assert cache.get_or_compute("k", version=(1, 10), compute=compute) == "value-1"
    # a new row → version changes → recompute
    assert cache.get_or_compute("k", version=(2, 11), compute=compute) == "value-2"
    assert calls["n"] == 2


def test_distinct_keys_are_independent():
    cache = VersionedCache()
    calls, compute = _counter()
    cache.get_or_compute("screener", version=1, compute=compute)
    cache.get_or_compute("seed", version=1, compute=compute)
    assert calls["n"] == 2   # different filter signatures cache separately


def test_eviction_beyond_max_entries():
    cache = VersionedCache(max_entries=2)
    calls, compute = _counter()
    cache.get_or_compute("a", 1, compute)   # value-1
    cache.get_or_compute("b", 1, compute)   # value-2
    cache.get_or_compute("c", 1, compute)   # value-3, evicts "a" (oldest)
    # "a" was evicted → recompute on next access
    assert cache.get_or_compute("a", 1, compute) == "value-4"
    # "c" still cached → no recompute
    n_before = calls["n"]
    cache.get_or_compute("c", 1, compute)
    assert calls["n"] == n_before


def test_touch_keeps_recently_used():
    cache = VersionedCache(max_entries=2)
    _, compute = _counter()
    cache.get_or_compute("a", 1, compute)
    cache.get_or_compute("b", 1, compute)
    cache.get_or_compute("a", 1, compute)   # touch "a" → "b" now oldest
    cache.get_or_compute("c", 1, compute)   # evicts "b", keeps "a"
    calls2, compute2 = _counter()
    cache.get_or_compute("a", 1, compute2)  # still cached
    assert calls2["n"] == 0
