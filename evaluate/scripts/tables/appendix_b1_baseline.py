"""Paper Appendix B.1 (`tab:baseline_aggregate`) — per-scanner finding counts
on the 17 unmodified Anthropic skills.

Reads $FINETUNE_BASELINE_ROOT/baseline_findings.csv with columns:
  scanner, skill, finding_count

Aggregates per scanner:
  - Skills (count of skills with >= 1 finding) / 17
  - Mean / Max / Total

Outputs:
  outputs/appendix_b1_baseline.{csv,tex}
"""
from __future__ import annotations

import csv
import os
import sys
from collections import defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

OUT = _ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

ROWS = [
    ("rule",     "skill-security-scan"),
    ("rule",     "Snyk Agent Scan"),
    ("rule",     "SkillScan"),
    ("prop_llm", "GPT-4o-mini"),
    ("prop_llm", "GPT-5.4-mini"),
    ("prop_llm", "GPT-5.4"),
    ("prop_llm", "Qwen2.5-Coder-7B (Fine-tuned + prefill)"),
]

GROUP_HEADERS = {
    "rule":     r"\textit{Rule-based / Commercial}",
    "prop_llm": r"\textit{Proprietary LLM}",
}


def main() -> int:
    root = os.environ.get("FINETUNE_BASELINE_ROOT")
    if not root:
        raise RuntimeError("FINETUNE_BASELINE_ROOT not set.")
    src = Path(root) / "baseline_findings.csv"
    if not src.is_file():
        raise RuntimeError(f"Expected {src} (one row per (scanner, skill, finding_count)).")

    per_scanner: dict[str, list[int]] = defaultdict(list)
    with src.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            per_scanner[r["scanner"]].append(int(r["finding_count"]))

    # CSV
    csv_path = OUT / "appendix_b1_baseline.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["scanner", "skills_with_findings", "n_skills", "mean", "max", "total"])
        for _, sc in ROWS:
            vals = per_scanner.get(sc, [])
            n_with = sum(1 for v in vals if v > 0)
            n_total = len(vals)
            mean = sum(vals) / n_total if n_total else 0.0
            mx = max(vals) if vals else 0
            tot = sum(vals)
            w.writerow([sc, n_with, n_total, f"{mean:.1f}", mx, tot])

    # LaTeX
    L = []
    L.append(r"\begin{table}[t]")
    L.append(r"\centering")
    L.append(r"\caption{Per-scanner finding counts on the 17 unmodified Anthropic skills. The Skills column reports the count and fraction of skills with at least one finding.}")
    L.append(r"\label{tab:baseline_aggregate}")
    L.append(r"\footnotesize")
    L.append(r"\setlength{\tabcolsep}{4pt}")
    L.append(r"\begin{tabular}{lrrrr}")
    L.append(r"\toprule")
    L.append(r"Scanner & Skills & Mean & Max & Total \\")
    L.append(r"\midrule")
    cur = None
    for group, sc in ROWS:
        if group != cur:
            L.append(rf"\multicolumn{{5}}{{l}}{{{GROUP_HEADERS[group]}}} \\")
            cur = group
        vals = per_scanner.get(sc, [])
        n_with = sum(1 for v in vals if v > 0)
        n_total = len(vals) or 17
        mean = sum(vals) / n_total if n_total else 0.0
        mx = max(vals) if vals else 0
        tot = sum(vals)
        L.append(rf"{sc} & {n_with}/{n_total} & {mean:.1f} & {mx} & {tot} \\")
    L.append(r"\bottomrule")
    L.append(r"\end{tabular}")
    L.append(r"\end{table}")
    (OUT / "appendix_b1_baseline.tex").write_text("\n".join(L), encoding="utf-8")

    print(f"[saved] {csv_path}")
    print(f"[saved] {OUT / 'appendix_b1_baseline.tex'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
