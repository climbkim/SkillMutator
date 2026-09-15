"""paths.py -- repo-relative path helpers for the analysis package.

`judge.py` imports `SKILLMUTATOR_REPO` (used only to locate a `.env` for the API
key) plus `scenario_dir` / `scanner_dir` (used by the full-scan-tree judging
flow, `judge_scanner_output`). The single-scan `judge_call` path needs only
`SKILLMUTATOR_REPO`.
"""
from __future__ import annotations

from pathlib import Path

# Framework root (one level up from this analysis/ package). `judge._get_client`
# does `load_dotenv(SKILLMUTATOR_REPO / ".env")`, so a repo-root .env is picked
# up; if OPENAI_API_KEY is already in the environment this is a no-op.
SKILLMUTATOR_REPO = Path(__file__).resolve().parent.parent


def scenario_dir(oracle: str, mode: str, skill: str, cat_folder: str,
                 it, *args, **kwargs) -> Path:
    """Directory of one (oracle, mode, skill, category, iter) scenario.

    Layout: <repo>/<oracle>/<mode>/<skill>/<cat_folder>/iter_<it>/. Only used by
    the full-tree flow (`judge_scanner_output`); the single-scan `judge_call`
    path does not call this.
    """
    return (SKILLMUTATOR_REPO / oracle / mode / skill / cat_folder / f"iter_{it}")


def scanner_dir(oracle: str, mode: str, skill: str, cat_folder: str,
                it, scanner_subpath: str = "", *args, **kwargs) -> Path:
    """Directory of one scanner's output under a scenario (see `scenario_dir`)."""
    base = scenario_dir(oracle, mode, skill, cat_folder, it)
    return (base / scanner_subpath) if scanner_subpath else base
