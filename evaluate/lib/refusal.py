"""Refusal classification + paper-canonical re-pinning.

The paper defines a refusal-free iteration as one whose `meta.json` has
`classification == "normal"`. For each (skill, category) scenario, the paper's
final evaluation uses the LATEST normal iteration ≤ K (re-pinning). Scenarios
with no normal iteration ≤ K are excluded from that iter's aggregate.

This module exposes:

  is_refusal_free(meta_path)        -> bool
  latest_normal_iter(iter_classifications, k)  -> int | None
  aggregate_scenario_final(rows, scanner_keys, k=4)  -> dict[(oracle,scanner)] -> {n, det, rate_pct}
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Sequence


REFUSAL_FREE_LABEL = "normal"


def read_classification(meta_path: Path | str) -> str | None:
    p = Path(meta_path)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("classification")
    except Exception:
        return None


def is_refusal_free(meta_path: Path | str) -> bool:
    return read_classification(meta_path) == REFUSAL_FREE_LABEL


def latest_normal_iter(iter_classifications: dict[int, str | None],
                       k: int) -> int | None:
    """Return the latest iter j <= k with classification == 'normal', or None."""
    for j in range(k, -1, -1):
        if iter_classifications.get(j) == REFUSAL_FREE_LABEL:
            return j
    return None


def aggregate_scenario_final(
    rows: Iterable[dict],
    scanner_keys: Sequence[str],
    iters: Sequence[int] = (0, 1, 2, 3, 4),
    k: int | None = None,
) -> dict[tuple[str, int, str], dict[str, int]]:
    """Aggregate per (oracle, iter, scanner) using refusal-free re-pinning.

    Each row is a dict with at least:
      oracle, skill, category, iter, classification, <scanner_key>=bool|None

    For each scenario (oracle, skill, category) and each target iter k in iters:
      - Find the latest j ≤ k with classification == 'normal'.
      - If none exists, scenario excluded from this (oracle, k, scanner) cell.
      - Else, use that j's per-scanner verdict.

    Returns dict[(oracle, k, scanner)] -> {"n": ..., "det": ...}.
    `rate_pct` can be computed as 100*det/n by the caller.
    """
    # Index rows by (oracle, skill, category) -> iter -> row
    by_scenario: dict[tuple[str, str, str], dict[int, dict]] = {}
    for r in rows:
        key = (r["oracle"], r["skill"], r["category"])
        by_scenario.setdefault(key, {})[int(r["iter"])] = r

    agg: dict[tuple[str, int, str], dict[str, int]] = {}
    target_iters = (k,) if k is not None else tuple(iters)

    for (oracle, _, _), iter_map in by_scenario.items():
        classifs = {it: row.get("classification") for it, row in iter_map.items()}
        for ki in target_iters:
            j = latest_normal_iter(classifs, ki)
            if j is None:
                continue
            src = iter_map[j]
            for sc in scanner_keys:
                v = src.get(sc)
                if v is None:
                    continue
                cell = agg.setdefault((oracle, ki, sc), {"n": 0, "det": 0})
                cell["n"] += 1
                if v:
                    cell["det"] += 1
    return agg
