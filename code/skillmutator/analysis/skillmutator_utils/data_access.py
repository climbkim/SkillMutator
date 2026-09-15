"""data_access.py — high-level walker for the unified data tree.

Once the tree is populated (Phase 2 build script), all RQ1/RQ2 analyses use
these helpers instead of touching raw scattered files.
"""
import csv, json, os
from pathlib import Path
from typing import Iterator, Optional

from .paths import (
    DATA_ROOT, ORACLES, MODES_BY_ORACLE, MAX_ITER_BY_MODE,
    scenario_dir, scanner_dir, llm_scanners_for, all_scanners_for,
)


def iter_scenarios(oracle: str, mode: str) -> Iterator[tuple[str, str]]:
    """Yield (skill, cat_folder) pairs that exist in the data tree."""
    base = DATA_ROOT / oracle / mode
    if not base.is_dir(): return
    for skill_dir in sorted(base.iterdir()):
        if not skill_dir.is_dir(): continue
        for cat_dir in sorted(skill_dir.iterdir()):
            if not cat_dir.is_dir(): continue
            yield skill_dir.name, cat_dir.name


def list_iters(oracle: str, mode: str, skill: str, cat_folder: str) -> list[int]:
    base = DATA_ROOT / oracle / mode / skill / cat_folder
    if not base.is_dir(): return []
    out = []
    for d in base.iterdir():
        if d.is_dir() and d.name.startswith("iter_"):
            try: out.append(int(d.name.split("_")[1]))
            except: pass
    return sorted(out)


def load_meta(oracle: str, mode: str, skill: str, cat_folder: str, it: int) -> Optional[dict]:
    p = scenario_dir(oracle, mode, skill, cat_folder, it) / "meta.json"
    if not p.is_file(): return None
    try: return json.loads(p.read_text(encoding="utf-8"))
    except: return None


def load_verdict(oracle: str, mode: str, skill: str, cat_folder: str, it: int, scanner_subpath: str) -> Optional[bool]:
    """scanner_subpath ∈ {'ss','snyk','llm/<scanner>'}. Returns the cached verdict.json's 'detected'."""
    p = scanner_dir(oracle, mode, skill, cat_folder, it, scanner_subpath) / "verdict.json"
    if not p.is_file(): return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        v = d.get("detected")
        return None if v is None else bool(v)
    except Exception:
        return None


def scanner_keys_for(oracle: str) -> list[str]:
    """Convenience: all scanner keys (subpaths) for this oracle."""
    return all_scanners_for(oracle)
