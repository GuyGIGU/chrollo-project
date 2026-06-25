"""Lightweight scan timing telemetry."""
from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone

from core.pipeline.cache import _cache_paths, _project_root, _read_meta, _write_meta
from core.pipeline.json_safety import to_json_safe


class ScanTimer:
    def __init__(self):
        self.started_at = datetime.now(timezone.utc)
        self._start = time.perf_counter()
        self.phases: dict[str, float] = {}

    @contextmanager
    def phase(self, name: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            self.phases[name] = round(time.perf_counter() - start, 2)

    def finish(self, **counts) -> dict:
        finished_at = datetime.now(timezone.utc)
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "total_s": round(time.perf_counter() - self._start, 2),
            "phases_s": dict(self.phases),
            "counts": counts,
        }


def persist_scan_metrics(metrics: dict) -> None:
    """Write latest metrics to cache_meta and append one history line."""
    _, meta_file = _cache_paths()
    meta = _read_meta(meta_file)
    meta["scan_metrics"] = metrics
    _write_meta(meta_file, meta)

    output_dir = os.path.join(_project_root(), "output")
    os.makedirs(output_dir, exist_ok=True)
    history_path = os.path.join(output_dir, "scan_metrics.jsonl")
    with open(history_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(to_json_safe(metrics), allow_nan=False) + "\n")


def format_scan_metrics(metrics: dict) -> str:
    phases = metrics.get("phases_s") or {}
    counts = metrics.get("counts") or {}
    parts = [
        f"total={metrics.get('total_s')}s",
        f"data={phases.get('market_data_fetch')}s",
        f"eval={phases.get('evaluation')}s",
        f"universe={counts.get('universe_tickers')}",
        f"evaluated={counts.get('evaluated_tickers')}",
        f"setups={counts.get('setups')}",
    ]
    return "Scan timing: " + ", ".join(parts)
