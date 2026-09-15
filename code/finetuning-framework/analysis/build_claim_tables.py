"""build_claim_tables.py -- render every fine-tuning-side paper float as a CSV,
laid out in a claims/-mirroring directory, FROM THIS RUN's scan data.

For each paper table/figure the fine-tuned scanner produces, this writes a CSV
with the paper's exact row/column STRUCTURE into

    <out_dir>/<claim_dir>/<float>.csv

Cells that this run actually measured are filled from the judge output; cells
that require additional runs (multi-variant / multi-model / other corpora) are
emitted as the paper's skeleton rows with status="full-mode" so the STRUCTURE
still matches the paper in demo mode. Values are always derived from the input,
never hard-coded, so the paper setting reproduces the paper's numbers.

Measured inputs (this run):
  --judge-csv  positives: judge_summary.csv over mutated (skill,category) pairs
               -> fine-tuned scanner recall (+ per-category recall).
  --neg-csv    negatives: judge_summary.csv over unmodified pairs (optional)
               -> precision / specificity for the Table XI metrics.

Usage:
    python analysis/build_claim_tables.py \\
        --judge-csv ${OUT}/scan/judge_summary.csv \\
        --neg-csv   ${OUT}/scan/judge_neg.csv \\
        --out-dir   ${OUT}/claim_tables \\
        --label     "demo (this run)"
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_DET_COLS = ("detected", "verdict", "judge_verdict")
_CAT_COLS = ("category", "cat", "attack_category")
_HIT = {"DETECTED", "PARTIAL"}
_TRUE = {"1", "true", "yes", "y", "t", "detected", "partial"}

FULL = "full-mode"      # cell needs additional runs; skeleton only
MEAS = "measured"       # filled from this run

# Paper float -> (claims mirror dir, output csv basename)
FLOATS = {
    "figure6":  ("claim12_rq3_comparison",     "figure6_rq3_comparison.csv"),
    "table11":  ("claim08_per_category_matrix", "table11_cell_metrics.csv"),
    "table8":   ("claim06_cost_envelope",       "table8_cost_envelope.csv"),
    "table6":   ("claim04_phase_ablation",      "table6_phase_ablation.csv"),
    "figure5":  ("claim11_finetune_base_models", "figure5_prefill_delta.csv"),
    "table7":   ("claim05_wild_clawhub",        "table7_wild_eval.csv"),
    "table10":  ("claim07_unmodified_baseline", "table10_baseline_aggregate.csv"),
}


def _pick(row, names):
    for n in names:
        if n in row and row[n] not in (None, ""):
            return n
    return None


def _is_hit(v):
    s = str(v).strip()
    return s.upper() in _HIT or s.lower() in _TRUE


def _load(csv_path):
    p = Path(csv_path)
    if not p.is_file():
        return [], None, None
    rows = list(csv.DictReader(p.open(encoding="utf-8")))
    if not rows:
        return [], None, None
    return rows, _pick(rows[0], _DET_COLS), _pick(rows[0], _CAT_COLS)


def _write(out_dir, key, header, rows):
    claim_dir, fname = FLOATS[key]
    d = Path(out_dir) / claim_dir
    d.mkdir(parents=True, exist_ok=True)
    path = d / fname
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return path.relative_to(out_dir)


def main() -> int:
    ap = argparse.ArgumentParser(description="Render fine-tuning-side paper floats as CSVs (claims-mirroring).")
    ap.add_argument("--judge-csv", required=True, help="positives judge_summary.csv (this run).")
    ap.add_argument("--neg-csv", default=None, help="negatives judge_summary.csv (unmodified pairs).")
    ap.add_argument("--out-dir", required=True, help="output root (claims-mirroring subdirs).")
    ap.add_argument("--label", default="this run", help="provenance label recorded in each CSV.")
    ap.add_argument("--qwen-usd-per-skill", type=float, default=0.00414,
                    help="local-scanner $/skill for the cost table (A100 batch estimate).")
    args = ap.parse_args()

    pos, pdet, pcat = _load(args.judge_csv)
    if not pos:
        sys.exit(f"[build_claim_tables] no rows in {args.judge_csv}")
    n_pos = len(pos)
    tp = sum(1 for r in pos if _is_hit(r[pdet]))
    recall = 100.0 * tp / n_pos if n_pos else 0.0

    neg, ndet, _ = _load(args.neg_csv) if args.neg_csv else ([], None, None)
    have_neg = bool(neg)
    fp = sum(1 for r in neg if _is_hit(r[ndet])) if have_neg else 0
    tn = (len(neg) - fp) if have_neg else 0

    lbl = args.label
    written = []

    # ---- Figure 6 (fig:rq3_finding1): scanner detection on n=pos -----------
    hdr = ["scanner", "recall_pct", "n", "status", "source"]
    rows = [
        ["skill-security-scan", "", n_pos, FULL, lbl],
        ["Snyk Agent Scan", "", n_pos, FULL, lbl],
        ["SkillScan", "", n_pos, FULL, lbl],
        ["GPT-4o-mini", "", n_pos, FULL, lbl],
        ["GPT-5.4-mini", "", n_pos, FULL, lbl],
        ["GPT-5.4", "", n_pos, FULL, lbl],
        ["Qwen-7B + ours (fine-tuned)", f"{recall:.1f}", n_pos, MEAS, lbl],
    ]
    written.append(_write(args.out_dir, "figure6", hdr, rows))

    # ---- Table XI (tab:cell_metrics): 5 classifier metrics -----------------
    if have_neg:
        precision = 100.0 * tp / (tp + fp) if (tp + fp) else 0.0
        specificity = 100.0 * tn / (tn + fp) if (tn + fp) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        bal = (recall + specificity) / 2.0
        st = MEAS
        vals = {"Recall (TPR)": recall, "Precision": precision, "F1": f1,
                "Specificity": specificity, "Balanced Accuracy": bal}
    else:
        st = FULL
        vals = {"Recall (TPR)": recall, "Precision": None, "F1": None,
                "Specificity": None, "Balanced Accuracy": None}
    hdr = ["metric", "value_pct", "status", "source"]
    rows = []
    for m in ["Recall (TPR)", "Precision", "F1", "Specificity", "Balanced Accuracy"]:
        v = vals[m]
        rows.append([m, f"{v:.1f}" if v is not None else "",
                     MEAS if (m == "Recall (TPR)" or have_neg) else FULL, lbl])
    written.append(_write(args.out_dir, "table11", hdr, rows))

    # ---- Table VIII (tab:cost_envelope): per-scan cost ---------------------
    ups = args.qwen_usd_per_skill
    upd = (ups / (recall / 100.0)) if recall > 0 else ""
    hdr = ["scanner", "usd_per_skill", "recall_pct", "usd_per_detection", "status", "source"]
    rows = [
        ["Qwen-7B + ours (local)", f"{ups:.5f}", f"{recall:.1f}",
         f"{upd:.5f}" if upd != "" else "", MEAS, lbl],
        ["GPT-4o-mini", "", "", "", FULL, lbl],
        ["GPT-5.4-mini", "", "", "", FULL, lbl],
        ["GPT-5.4", "", "", "", FULL, lbl],
    ]
    written.append(_write(args.out_dir, "table8", hdr, rows))

    # ---- Table VI (tab:finetune_rq2): four-phase schema ablation -----------
    # demo fills only the final "+prefill" row (the released adapter == prefill).
    hdr = ["schema", "detection_rate_pct", "status", "source"]
    rows = [
        ["Phase 1 (Purpose Grounding)", "", FULL, lbl],
        ["+ Phase 2 (Out-of-Scope Detection)", "", FULL, lbl],
        ["+ Phase 3 (Principle Reasoning)", "", FULL, lbl],
        ["+ Phase 4 (Category Labeling)", "", FULL, lbl],
        ["+ deterministic refinement", "", FULL, lbl],
        ["+ prefill (Phase 4 header forced)", f"{recall:.1f}", MEAS, lbl],
    ]
    written.append(_write(args.out_dir, "table6", hdr, rows))

    # ---- Figure 5 (fig:prefill_delta_comparison): 4 base families ----------
    hdr = ["model", "base_pct", "no_prefill_pct", "prefill_pct", "status", "source"]
    rows = [
        ["Qwen2.5-Coder-7B-Instruct", "", "", f"{recall:.1f}", MEAS, lbl],
        ["Llama-3.1-8B-Instruct", "", "", "", FULL, lbl],
        ["Mistral-7B-Instruct-v0.3", "", "", "", FULL, lbl],
        ["Gemma-2-9b-it", "", "", "", FULL, lbl],
    ]
    written.append(_write(args.out_dir, "figure5", hdr, rows))

    # ---- Table VII (tab:wild_eval): in-the-wild ClawHub (needs corpus) -----
    hdr = ["stratum", "accuracy_pct", "status", "source"]
    rows = [
        ["clean", "", FULL, lbl],
        ["suspicious/LOW", "", FULL, lbl],
        ["suspicious/MED", "", FULL, lbl],
        ["suspicious/HIGH", "", FULL, lbl],
        ["suspicious/CRIT", "", FULL, lbl],
        ["Aggregate (Accuracy)", "", FULL, lbl],
        ["Aggregate (FPR)", "", FULL, lbl],
    ]
    written.append(_write(args.out_dir, "table7", hdr, rows))

    # ---- Table X (tab:baseline_aggregate): finding counts on unmodified ----
    # demo fills the fine-tuned-scanner "skills-with-finding" count if a negative
    # (unmodified) scan was provided.
    qwen_skills = f"{fp}/{len(neg)}" if have_neg else ""
    hdr = ["scanner", "skills_with_finding", "mean", "max", "total", "status", "source"]
    rows = [
        ["skill-security-scan", "", "", "", "", FULL, lbl],
        ["Snyk Agent Scan", "", "", "", "", FULL, lbl],
        ["SkillScan", "", "", "", "", FULL, lbl],
        ["GPT-4o-mini", "", "", "", "", FULL, lbl],
        ["GPT-5.4-mini", "", "", "", "", FULL, lbl],
        ["GPT-5.4", "", "", "", "", FULL, lbl],
        ["Qwen2.5-Coder-7B (fine-tuned + prefill)", qwen_skills, "", "", "",
         MEAS if have_neg else FULL, lbl],
    ]
    written.append(_write(args.out_dir, "table10", hdr, rows))

    # ---- per-category recall (positive side of Table XI) -------------------
    if pcat:
        per = defaultdict(lambda: [0, 0])
        for r in pos:
            c = r.get(pcat) or "(uncategorized)"
            per[c][1] += 1
            per[c][0] += 1 if _is_hit(r[pdet]) else 0
        d = Path(args.out_dir) / FLOATS["table11"][0]
        with (d / "table11_per_category_recall.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["attack_category", "detected", "n", "recall_pct"])
            for c in sorted(per):
                h, t = per[c]
                w.writerow([c, h, t, f"{100.0*h/t:.1f}" if t else "0.0"])

    print(f"[build_claim_tables] label={lbl}  positives n={n_pos} detected={tp} recall={recall:.1f}%"
          + (f"  negatives n={len(neg)} fp={fp}" if have_neg else "  (no negatives -> Table XI/X metrics skeleton)"))
    for rel in written:
        print(f"  wrote {rel}")
    print(f"[build_claim_tables] output root: {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
