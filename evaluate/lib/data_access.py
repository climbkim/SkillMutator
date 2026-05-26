"""Walk the unified SkillMutator-data tree.

Expected layout:

    <DATA_ROOT>/<oracle>/<mode>/<skill>/<cat_folder>/iter_K/
        ├── meta.json
        ├── injected_content.md
        ├── ss/{report.md, verdict.json}
        ├── snyk/{report.md, verdict.json}
        └── llm/<scanner>/{scan.md, judge_v2.json, verdict.json}

`load_oracle_rows(oracle, mode="select")` returns one row per (skill, cat, iter)
combination with `classification` (from `meta.json`) and a `detected` flag per
scanner (ss, snyk, and the matching LLM self-scanner for the oracle).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterator


# Canonical oracle list used by every paper builder.
ORACLES = ("gpt-4o-mini", "gpt-5.4-mini", "gpt-5.4")

# Mapping from oracle name to its self-LLM scanner directory.
LLM_SELF = {
    "gpt-4o-mini":  "gpt-4o-mini-self",
    "gpt-5.4-mini": "gpt-5.4-mini-self",
    "gpt-5.4":      "gpt-5.4-self",
}


def data_root() -> Path:
    root = os.environ.get("SKILLMUTATOR_DATA_ROOT")
    if not root:
        raise RuntimeError(
            "SKILLMUTATOR_DATA_ROOT not set. "
            "Export it to point at your unified data tree (see evaluate/README.md)."
        )
    p = Path(root)
    if not p.is_dir():
        raise RuntimeError(f"SKILLMUTATOR_DATA_ROOT={root} is not a directory.")
    return p


def read_detected(verdict_path: Path) -> bool | None:
    if not verdict_path.is_file():
        return None
    try:
        return bool(json.loads(verdict_path.read_text(encoding="utf-8")).get("detected"))
    except Exception:
        return None


def read_classification(meta_path: Path) -> str | None:
    if not meta_path.is_file():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8")).get("classification")
    except Exception:
        return None


def iter_scenarios(root: Path, oracle: str, mode: str = "select") -> Iterator[Path]:
    """Yield each <cat_dir> under <root>/<oracle>/<mode>/<skill>/<cat>/."""
    base = root / oracle / mode
    if not base.is_dir():
        return
    for skill_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        for cat_dir in sorted(p for p in skill_dir.iterdir() if p.is_dir()):
            yield cat_dir


def load_oracle_rows(oracle: str,
                     mode: str = "select",
                     iters: tuple[int, ...] = (0, 1, 2, 3, 4),
                     root: Path | None = None) -> list[dict]:
    """Return rows: one per (skill, cat, iter) under oracle/mode.

    For oracles without a registered LLM self-scanner (e.g. ``claude-opus-4-7``,
    where the IER feedback loop is run by Claude itself rather than a separate
    `llm/<name>-self` directory), the ``llm`` column is set to ``None`` and
    only ``ss`` / ``snyk`` / ``classification`` are populated.
    """
    root = root or data_root()
    llm_self = LLM_SELF.get(oracle)
    rows: list[dict] = []
    for cat_dir in iter_scenarios(root, oracle, mode):
        skill = cat_dir.parent.name
        category = cat_dir.name
        for it in iters:
            iter_dir = cat_dir / f"iter_{it}"
            if not iter_dir.is_dir():
                continue
            llm_det = None
            if llm_self is not None:
                llm_det = read_detected(iter_dir / "llm" / llm_self / "verdict.json")
            rows.append({
                "oracle": oracle,
                "mode": mode,
                "skill": skill,
                "category": category,
                "iter": it,
                "classification": read_classification(iter_dir / "meta.json"),
                "ss":   read_detected(iter_dir / "ss" / "verdict.json"),
                "snyk": read_detected(iter_dir / "snyk" / "verdict.json"),
                "llm":  llm_det,
            })
    return rows


def load_all_rows(mode: str = "select",
                  iters: tuple[int, ...] = (0, 1, 2, 3, 4),
                  oracles: tuple[str, ...] = ORACLES,
                  root: Path | None = None) -> list[dict]:
    """Load all oracles into a single flat list."""
    out: list[dict] = []
    root = root or data_root()
    for o in oracles:
        out.extend(load_oracle_rows(o, mode=mode, iters=iters, root=root))
    return out
