"""Paper Table III (`tab:cross_matrix`) — cross-scanner detection rate matrix.

Reads the unified Skillmutator-data tree (env: SKILLMUTATOR_DATA_ROOT) and
emits the 9-row × 4-oracle detection-rate matrix using paper-canonical
refusal-free re-pinning at iter K = 4 (= display iter 5).

Layout (matches paper):
  Rule-based / Commercial: skill-security-scan, Snyk Agent Scan, SkillScan
  Prompt-Injection Detectors: LLM-Guard, PIGuard, DataSentinel
  Proprietary LLM: GPT-4o-mini, GPT-5.4-mini, GPT-5.4

The PI-detectors and SkillScan rows expect separate aggregate inputs since
they live outside the main per-iter Skillmutator-data tree:
  env FINETUNE_BASELINE_ROOT/{skillscan,llmguard,piguard,datasentinel}/<oracle>.csv
  (one row per scenario with column `detected`).

Outputs:
  outputs/table3_cross_matrix.csv
  outputs/table3_cross_matrix.tex
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from lib.data_access import ORACLES, load_all_rows
from lib.refusal import aggregate_scenario_final

OUT = _ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

# Column order in the paper table.
COL_ORACLES = ("gpt-4o-mini", "gpt-5.4-mini", "gpt-5.4", "claude-opus-4-7")
COL_LABELS = {
    "gpt-4o-mini":     "GPT-4o-mini",
    "gpt-5.4-mini":    "GPT-5.4-mini",
    "gpt-5.4":         "GPT-5.4",
    "claude-opus-4-7": "Claude Opus-4.7",
}

# Row layout in the paper table. Each entry: (group_label, scanner_id, display_name)
# Aggregate keys ("ss", "snyk", "llm") map to columns from the per-iter walk.
# The remaining scanners (SkillScan, LLM-Guard, PIGuard, DataSentinel) come
# from separate aggregate inputs (see read_external_aggregate below).
ROWS = [
    ("rule",     "ss",   "skill-security-scan"),
    ("rule",     "snyk", "Snyk Agent Scan"),
    ("rule",     "skillscan", "SkillScan"),
    ("pi",       "llmguard",     "LLM-Guard"),
    ("pi",       "piguard",      "PIGuard"),
    ("pi",       "datasentinel", "DataSentinel"),
    ("prop_llm", "gpt-4o-mini-llm",  "GPT-4o-mini"),
    ("prop_llm", "gpt-5.4-mini-llm", "GPT-5.4-mini"),
    ("prop_llm", "gpt-5.4-llm",      "GPT-5.4"),
]

GROUP_HEADERS = {
    "rule":     r"\textit{Rule-based / Commercial}",
    "pi":       r"\textit{Prompt-Injection Detectors}",
    "prop_llm": r"\textit{Proprietary LLM}",
}


def read_external_aggregate(scanner: str, oracle: str) -> dict | None:
    """Read aggregate detection rate from FINETUNE_BASELINE_ROOT/<scanner>/<oracle>.csv.

    Each CSV row has at least column `detected` (true/false). Returns
    {"n": ..., "det": ...} or None if file missing.
    """
    root = os.environ.get("FINETUNE_BASELINE_ROOT")
    if not root:
        return None
    p = Path(root) / scanner / f"{oracle}.csv"
    if not p.is_file():
        return None
    n = det = 0
    with p.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            n += 1
            if str(r.get("detected", "")).strip().lower() == "true":
                det += 1
    return {"n": n, "det": det}


def fetch_cell(scanner_id: str, oracle: str, repin_agg: dict) -> dict | None:
    """Return {n, det} for (scanner_id, oracle) or None when data is unavailable."""
    if scanner_id in ("ss", "snyk"):
        return repin_agg.get((oracle, 4, scanner_id))
    if scanner_id == f"{oracle}-llm":
        return repin_agg.get((oracle, 4, "llm"))
    # Other LLM cross-pairs (e.g. gpt-5.4-mini scanner on gpt-5.4 oracle) require
    # a separate cross-llm walk — collected externally and dropped under
    # FINETUNE_BASELINE_ROOT/gpt-{name}-llm/<oracle>.csv.
    name_map = {
        "gpt-4o-mini-llm":  "gpt-4o-mini",
        "gpt-5.4-mini-llm": "gpt-5.4-mini",
        "gpt-5.4-llm":      "gpt-5.4",
    }
    if scanner_id in name_map:
        # Only the (scanner == oracle) self-pair comes from repin_agg; cross-
        # pairs come from the external aggregate input.
        scanner_dir = name_map[scanner_id]
        if scanner_dir != oracle:
            return read_external_aggregate(f"{scanner_dir}-llm", oracle)
    # SkillScan + PI detectors come from external aggregates.
    return read_external_aggregate(scanner_id, oracle)


def main() -> int:
    # Per-iter walk (for ss, snyk, llm self-pairs at iter 4 re-pinned).
    rows = load_all_rows(mode="select")
    repin_agg = aggregate_scenario_final(rows, scanner_keys=("ss", "snyk", "llm"), k=4)

    # Build matrix
    matrix: list[dict] = []
    for group, scanner_id, display in ROWS:
        cells = {}
        for o in COL_ORACLES:
            cell = fetch_cell(scanner_id, o, repin_agg)
            cells[o] = cell
        matrix.append({"group": group, "scanner": display, "cells": cells})

    # CSV
    csv_path = OUT / "table3_cross_matrix.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["group", "scanner"] + [COL_LABELS[o] + "_rate_pct" for o in COL_ORACLES])
        for row in matrix:
            line = [row["group"], row["scanner"]]
            for o in COL_ORACLES:
                cell = row["cells"][o]
                if cell and cell["n"]:
                    line.append(f"{100.0 * cell['det'] / cell['n']:.2f}")
                else:
                    line.append("")
            w.writerow(line)

    # LaTeX
    L = []
    L.append(r"\begin{table}[t]")
    L.append(r"\centering")
    L.append(r"\caption{Cross-scanner detection rate (\%) across four adversarial-oracle datasets.}")
    L.append(r"\label{tab:cross_matrix}")
    L.append(r"\resizebox{\columnwidth}{!}{")
    L.append(r"\begin{tabular}{l" + "r" * len(COL_ORACLES) + "}")
    L.append(r"\toprule")
    L.append(r"\textbf{Scanner} & "
             + " & ".join(rf"\textbf{{{COL_LABELS[o]}}}" for o in COL_ORACLES)
             + r" \\")
    L.append(r"\midrule")
    cur_group = None
    for row in matrix:
        if row["group"] != cur_group:
            L.append(rf"\multicolumn{{{len(COL_ORACLES) + 1}}}{{l}}{{{GROUP_HEADERS[row['group']]}}} \\")
            cur_group = row["group"]
        cells_fmt = []
        for o in COL_ORACLES:
            cell = row["cells"][o]
            cells_fmt.append(f"{100.0 * cell['det'] / cell['n']:.2f}\\%" if cell and cell["n"] else r"\textemdash")
        L.append(rf"{row['scanner']} & " + " & ".join(cells_fmt) + r" \\")
    L.append(r"\bottomrule")
    L.append(r"\end{tabular}}")
    L.append(r"\end{table}")
    (OUT / "table3_cross_matrix.tex").write_text("\n".join(L), encoding="utf-8")

    print(f"[saved] {csv_path}")
    print(f"[saved] {OUT / 'table3_cross_matrix.tex'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
