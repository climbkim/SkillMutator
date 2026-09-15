"""paths.py — canonical layout of the unified data tree.

After the May-2026 consolidation, the data tree at ${SKILLMUTATOR_DATA_ROOT}/
is the single source of truth. All runtime analyses read from it; the original
scattered scanner outputs (in skillmutator-github/experiments and
RQ2/_extension/) have been deleted, so the tree is the only persistent state.

Tree:
  Skillmutator-data/
    <oracle>/<mode>/<skill>/<cat_folder>/iter_K/
      meta.json                         {oracle, mode, skill, cat_folder,
                                         cat_label, iter, ts, scenario_title,
                                         classification}
      injected_content.md               attack ground truth (<=1500 chars/file)
      ss/{report.md, verdict.json}      SS strict count-delta criterion
      snyk/{report.md, verdict.json}    Snyk lenient identity-delta criterion
      llm/<scanner>/{scan.md, judge_v2.json, verdict.json}
                                        scanner output + GPT-5.4 v2 judge

Scanner naming inside llm/:
  <oracle>-self : the oracle's matched LLM
  gpt-4o-mini   : cross-LLM (only for gpt-5.4 oracle)
  gpt-5.4-mini  : cross-LLM (only for gpt-5.4 oracle)
"""
import os
from pathlib import Path

# === unified tree (the source of truth) ===
# Override via $SKILLMUTATOR_DATA_ROOT to point at your local Skillmutator-data
# tree. The default below is the relative path used inside this repo for CI
# smoke tests; reproducing the paper requires a populated data tree (see
# docs/REPRODUCE.md in the repo root).
DATA_ROOT = Path(os.environ.get("SKILLMUTATOR_DATA_ROOT", "./data/skillmutator-data"))

# === enumerations ===
ORACLES = ["gpt-4o-mini", "gpt-5.4-mini", "gpt-5.4"]
MODES_BY_ORACLE = {
    "gpt-4o-mini":  ["select"],
    "gpt-5.4-mini": ["select"],
    "gpt-5.4":      ["select", "no-select"],
}
MAX_ITER_BY_MODE = {"select": 4, "no-select": 2}


# === Optional auxiliary paths (used only by one-off rebuild tooling) ===
# These point at locations specific to the original development environment
# and are NOT required by the runtime analysis scripts. Override via env var
# if you need to re-run the historical data-builders that lived under
# `_historical/` (excluded from the public release).
SKILLMUTATOR_REPO = Path(os.environ.get("SKILL_MUTATOR_REPO", "../skill-mutator"))
EXPERIMENTS       = SKILLMUTATOR_REPO / "experiments"
BASELINE_SKILLS   = SKILLMUTATOR_REPO / "skills"


def data_root() -> Path:
    return DATA_ROOT


def scenario_dir(oracle: str, mode: str, skill: str, cat_folder: str, it: int) -> Path:
    return DATA_ROOT / oracle / mode / skill / cat_folder / f"iter_{it}"


def scanner_dir(oracle: str, mode: str, skill: str, cat_folder: str, it: int, scanner_subpath: str) -> Path:
    """scanner_subpath in {'ss', 'snyk', 'llm/<scanner>'}."""
    return scenario_dir(oracle, mode, skill, cat_folder, it) / scanner_subpath


def llm_scanners_for(oracle: str) -> list:
    """LLM scanner directory names under llm/ for this oracle.

    Each oracle has its matched self-scanner plus the two cross-LLM scanners.
    Cross-scanner data was populated by skillmutator_utils/_historical/
    fill_cross_scanner_cells.py (May-2026).
    """
    all_llms = ["gpt-4o-mini", "gpt-5.4-mini", "gpt-5.4"]
    out = [f"{oracle}-self"]
    for sc in all_llms:
        if sc != oracle:
            out.append(sc)
    return out


def all_scanners_for(oracle: str) -> list:
    """All scanner subpaths for verdict aggregation."""
    return ["ss", "snyk"] + [f"llm/{s}" for s in llm_scanners_for(oracle)]


CAT_FOLDER_FROM_LABEL = {
    "Advertising Injection":     "advertising_injection",
    "Brand Hijacking":           "brand_hijacking",
    "Code Quality Degradation":  "code_quality_degradation",
    "Configuration Weakening":   "configuration_weakening",
    "Data Exfiltration":         "data_exfiltration",
    "Data Integrity Risks":      "data_integrity_risks",
    "Disruption & Interference": "disruption_interference",
    "False Attribution":         "false_attribution",
    "Information Gathering":     "information_gathering",
    "Over-engineering":          "over-engineering",
    "Persistence Control":       "persistence_control",
    "Supply Chain Attack":       "supply_chain_attack",
}
CAT_LABEL_FROM_FOLDER = {v: k for k, v in CAT_FOLDER_FROM_LABEL.items()}


def cat_to_folder(label: str) -> str:
    if label in CAT_FOLDER_FROM_LABEL:
        return CAT_FOLDER_FROM_LABEL[label]
    return label.lower().replace(" & ", "_").replace(" ", "_")


def folder_to_label(folder: str) -> str:
    if folder in CAT_LABEL_FROM_FOLDER:
        return CAT_LABEL_FROM_FOLDER[folder]
    return folder.replace("_", " ").title()
