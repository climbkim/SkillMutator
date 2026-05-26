"""Paper Appendix B.2 figure (`fig:fp_per_cat`) — per-category FP cell count
for the fine-tuned Qwen scanner on the 17 unmodified Anthropic skills.

Reads $FINETUNE_BASELINE_ROOT/cells_unmodified.csv (columns: skill, category,
fired_bool). For each canonical category, counts how many of the 17 skills
have at least one `## Phase 4` bullet of that category that is not `(none)`.

Outputs (small fixed-width table in the paper):
  outputs/figure_fp_per_cat.csv
  outputs/figure_fp_per_cat.tex
"""
from __future__ import annotations

import csv
import os
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

OUT = _ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

# 13 canonical attack categories ordered as in the paper Appendix B figure.
CATEGORIES = [
    "Information Gathering",
    "Code Quality Degradation",
    "Data Integrity Risks",
    "Brand Hijacking",
    "Over-engineering",
    "Persistence Control",
    "Supply Chain Attack",
    "Advertising Injection",
    "Configuration Weakening",
    "Data Exfiltration",
    "Disruption \\& Interference",
    "False Attribution",
    "Privilege Escalation",
]


def main() -> int:
    root = os.environ.get("FINETUNE_BASELINE_ROOT")
    if not root:
        raise RuntimeError("FINETUNE_BASELINE_ROOT not set.")
    src = Path(root) / "cells_unmodified.csv"
    if not src.is_file():
        raise RuntimeError(f"missing input: {src}")

    # Per (skill, category): aggregate by category, counting any skill that fires
    fired_skills_per_cat: dict[str, set[str]] = {c: set() for c in CATEGORIES}
    with src.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if str(r.get("fired_bool", "")).strip().lower() == "true":
                cat = r.get("category", "")
                if cat in fired_skills_per_cat:
                    fired_skills_per_cat[cat].add(r.get("skill", ""))

    # CSV
    csv_path = OUT / "figure_fp_per_cat.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["category", "skills_with_fp"])
        for c in CATEGORIES:
            w.writerow([c, len(fired_skills_per_cat[c])])

    # LaTeX (matches paper's small fixed table inside a figure environment)
    L = []
    L.append(r"\begin{figure}[t]")
    L.append(r"\centering")
    L.append(r"\begin{tabular}{lc}")
    L.append(r"\toprule")
    L.append(r"\textbf{Attack Category} & \textbf{FP cells / 17 skills} \\")
    L.append(r"\midrule")
    for c in CATEGORIES:
        L.append(rf"{c} & {len(fired_skills_per_cat[c])} \\")
    L.append(r"\bottomrule")
    L.append(r"\end{tabular}")
    L.append(r"\caption{Per-category FP cell count for the fine-tuned Qwen scanner on the 17 unmodified Anthropic skills.}")
    L.append(r"\label{fig:fp_per_cat}")
    L.append(r"\end{figure}")
    (OUT / "figure_fp_per_cat.tex").write_text("\n".join(L), encoding="utf-8")

    print(f"[saved] {csv_path}")
    print(f"[saved] {OUT / 'figure_fp_per_cat.tex'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
