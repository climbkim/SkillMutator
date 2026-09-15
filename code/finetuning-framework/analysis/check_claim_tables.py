"""check_claim_tables.py -- verify the generated claim CSVs match the paper's
table/figure STRUCTURE (columns + row labels).

This is the "checkable" step for the finetuning reproduction: it does NOT compare
values against the paper (demo values differ), it asserts that each CSV produced
by build_claim_tables.py has the paper float's exact columns and row labels, and
that every cell marked status="measured" is actually populated. Run it after
build_claim_tables.py; prints PASS/FAIL per float and exits non-zero on any FAIL.

Usage:
    python analysis/check_claim_tables.py --tables-dir ${OUT}/claim_tables
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# claim_dir/filename -> (expected columns, first-column label of every row, key-cell-col)
# The "measured-required" column, when set, must be non-empty on rows whose
# status == "measured".
EXPECT = {
    "claim12_rq3_comparison/figure6_rq3_comparison.csv": {
        "cols": ["scanner", "recall_pct", "n", "status", "source"],
        "rows": ["skill-security-scan", "Snyk Agent Scan", "SkillScan", "GPT-4o-mini",
                 "GPT-5.4-mini", "GPT-5.4", "Qwen-7B + ours (fine-tuned)"],
        "measured_col": "recall_pct",
    },
    "claim08_per_category_matrix/table11_cell_metrics.csv": {
        "cols": ["metric", "value_pct", "status", "source"],
        "rows": ["Recall (TPR)", "Precision", "F1", "Specificity", "Balanced Accuracy"],
        "measured_col": "value_pct",
    },
    "claim06_cost_envelope/table8_cost_envelope.csv": {
        "cols": ["scanner", "usd_per_skill", "recall_pct", "usd_per_detection", "status", "source"],
        "rows": ["Qwen-7B + ours (local)", "GPT-4o-mini", "GPT-5.4-mini", "GPT-5.4"],
        "measured_col": "recall_pct",
    },
    "claim04_phase_ablation/table6_phase_ablation.csv": {
        "cols": ["schema", "detection_rate_pct", "status", "source"],
        "rows": ["Phase 1 (Purpose Grounding)", "+ Phase 2 (Out-of-Scope Detection)",
                 "+ Phase 3 (Principle Reasoning)", "+ Phase 4 (Category Labeling)",
                 "+ deterministic refinement", "+ prefill (Phase 4 header forced)"],
        "measured_col": "detection_rate_pct",
    },
    "claim11_finetune_base_models/figure5_prefill_delta.csv": {
        "cols": ["model", "base_pct", "no_prefill_pct", "prefill_pct", "status", "source"],
        "rows": ["Qwen2.5-Coder-7B-Instruct", "Llama-3.1-8B-Instruct",
                 "Mistral-7B-Instruct-v0.3", "Gemma-2-9b-it"],
        "measured_col": "prefill_pct",
    },
    "claim05_wild_clawhub/table7_wild_eval.csv": {
        "cols": ["stratum", "accuracy_pct", "status", "source"],
        "rows": ["clean", "suspicious/LOW", "suspicious/MED", "suspicious/HIGH",
                 "suspicious/CRIT", "Aggregate (Accuracy)", "Aggregate (FPR)"],
        "measured_col": None,
    },
    "claim07_unmodified_baseline/table10_baseline_aggregate.csv": {
        "cols": ["scanner", "skills_with_finding", "mean", "max", "total", "status", "source"],
        "rows": ["skill-security-scan", "Snyk Agent Scan", "SkillScan", "GPT-4o-mini",
                 "GPT-5.4-mini", "GPT-5.4", "Qwen2.5-Coder-7B (fine-tuned + prefill)"],
        "measured_col": None,
    },
}


def check_one(path: Path, spec: dict) -> list[str]:
    errs: list[str] = []
    if not path.is_file():
        return [f"missing file: {path}"]
    rows = list(csv.reader(path.open(encoding="utf-8")))
    if not rows:
        return [f"empty file: {path}"]
    header, body = rows[0], rows[1:]
    if header != spec["cols"]:
        errs.append(f"columns {header} != expected {spec['cols']}")
    got_labels = [r[0] for r in body if r]
    if got_labels != spec["rows"]:
        errs.append(f"row labels {got_labels} != expected {spec['rows']}")
    mc = spec.get("measured_col")
    if mc and mc in header and not errs:
        si = header.index("status")
        ci = header.index(mc)
        for r in body:
            if len(r) > max(si, ci) and r[si] == "measured" and not r[ci].strip():
                errs.append(f"row '{r[0]}' status=measured but '{mc}' is empty")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser(description="Structurally verify generated claim CSVs against the paper schema.")
    ap.add_argument("--tables-dir", required=True, help="Root written by build_claim_tables.py.")
    args = ap.parse_args()
    root = Path(args.tables_dir)

    all_ok = True
    for rel, spec in EXPECT.items():
        errs = check_one(root / rel, spec)
        if errs:
            all_ok = False
            print(f"[FAIL] {rel}")
            for e in errs:
                print(f"        - {e}")
        else:
            print(f"[OK]   {rel}  (paper structure matched)")

    print()
    print("ALL STRUCTURES MATCH PAPER" if all_ok else "STRUCTURE MISMATCH")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
