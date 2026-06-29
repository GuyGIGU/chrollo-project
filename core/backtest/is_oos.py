"""In-sample / out-of-sample split keyed on the frozen engine_config_version.

A standalone-edge claim is only trustworthy if it holds OUT of sample. The frozen
engine stamps every archived row with ``engine_config_version`` (the sha256 of
core/freeze/manifest). Rows produced by the SAME config version are one regime;
when the config changes, later rows are a natural out-of-sample test of the edge
measured on the earlier config.

Split policy (deliberately simple, honest about a young archive):
  * If ``engine_config_version`` is ABSENT or single-valued, there is only one
    config epoch — no IS/OOS split is possible. The harness says so and treats the
    whole archive as in-sample (degrades gracefully, never crashes). This is the
    current production state (the column hasn't been backfilled onto old rows).
  * If MULTIPLE versions are present, the EARLIEST version(s) by first-seen date
    are in-sample and the LATEST is out-of-sample, so the split respects time.

Pure: DataFrame in, split dicts out. No I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

CONFIG_COL = "engine_config_version"


@dataclass(frozen=True)
class SplitResult:
    available: bool                 # False = can't split (single/absent config)
    reason: Optional[str]
    n_versions: int
    is_versions: tuple[str, ...]    # config hashes assigned to in-sample
    oos_versions: tuple[str, ...]   # config hashes assigned to out-of-sample
    is_index: tuple                 # row indices (df.index values) for IS
    oos_index: tuple                # row indices for OOS

    def as_dict(self) -> dict:
        return {
            "available": self.available,
            "reason": self.reason,
            "n_versions": self.n_versions,
            "is_versions": list(self.is_versions),
            "oos_versions": list(self.oos_versions),
            "n_is": len(self.is_index),
            "n_oos": len(self.oos_index),
        }


def _version_first_seen(df: pd.DataFrame) -> dict[str, str]:
    """Earliest scan_date per config version (for time-ordering the split)."""
    out: dict[str, str] = {}
    for ver, sub in df.dropna(subset=[CONFIG_COL]).groupby(CONFIG_COL):
        dates = sub["scan_date"].astype(str)
        out[str(ver)] = dates.min() if len(dates) else ""
    return out


def split_is_oos(df: pd.DataFrame) -> SplitResult:
    """Split the archive into in-sample / out-of-sample by config version.

    Degrades gracefully: an absent or single-valued ``engine_config_version``
    column yields ``available=False`` with the whole frame treated as in-sample.
    """
    n = len(df)
    if CONFIG_COL not in df.columns:
        return SplitResult(
            available=False,
            reason=(
                f"archive has no '{CONFIG_COL}' column — pre-freeze rows carry no "
                "engine stamp. Treating the whole archive as a single in-sample "
                "epoch. An IS/OOS split becomes possible once stamped rows from a "
                "second config version accrue."
            ),
            n_versions=0, is_versions=(), oos_versions=(),
            is_index=tuple(df.index), oos_index=(),
        )

    versions = df[CONFIG_COL].dropna()
    distinct = sorted(set(versions.astype(str)))
    if len(distinct) <= 1:
        only = distinct[0] if distinct else None
        return SplitResult(
            available=False,
            reason=(
                f"only {len(distinct)} engine_config_version present "
                f"({'none stamped' if only is None else 'single config epoch'}). "
                "No IS/OOS split possible yet; whole archive is in-sample. The "
                "split activates when a second frozen config version produces rows."
            ),
            n_versions=len(distinct),
            is_versions=tuple(distinct), oos_versions=(),
            is_index=tuple(df.index), oos_index=(),
        )

    # Multiple versions: order by first-seen date; newest version is OOS.
    first_seen = _version_first_seen(df)
    ordered = sorted(distinct, key=lambda v: (first_seen.get(v, ""), v))
    oos_versions = (ordered[-1],)
    is_versions = tuple(ordered[:-1])

    is_mask = df[CONFIG_COL].astype(str).isin(is_versions)
    oos_mask = df[CONFIG_COL].astype(str).isin(oos_versions)
    return SplitResult(
        available=True,
        reason=None,
        n_versions=len(distinct),
        is_versions=is_versions, oos_versions=oos_versions,
        is_index=tuple(df.index[is_mask]), oos_index=tuple(df.index[oos_mask]),
    )
