"""build_tab_phase_ablation.py — paper Finding 3 (four-phase schema ablation).

Aggregates per-variant `judge_summary.csv` into the cumulative phase-ablation
table (paper Table V; headline final value is 88.16 % = 67/76 with refine +
forced Phase 4 prefill, see paper §6.4 Finding 3):

    P1                          -> 1.32 % (1/76)
    + P2                        -> 25.00 %
    + P3                        -> 57.89 %
    + P4 (no-prefill)           -> 67.11 %
    + Forced Prefix Pre-filling -> 88.16 % (67/76)  -- paper headline

Expected directory layout under --root (the `D3-` prefix is the legacy on-disk
data-directory tag and is retained for backward compatibility with existing
evaluation runs; the table-generation script emits paper-facing display labels):

    <root>/D3-P1_noprefill/judge_summary.csv
    <root>/D3-P12_noprefill/judge_summary.csv
    <root>/D3-P123_noprefill/judge_summary.csv
    <root>/D3-P1234_noprefill/judge_summary.csv
    <root>/D3-P1234_prefill/judge_summary.csv

Outputs:
    outputs/tab_phase_ablation.csv
    outputs/tab_phase_ablation.tex
"""
import argparse
import csv
import sys
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROW_LAYOUT = [
    # (data-dir suffix, short label, paper-facing display label)
    ("D3-P1_noprefill",     "P1",                 r"Phase 1 (Purpose Grounding)"),
    ("D3-P12_noprefill",    "P1-2",               r"+ Phase 2 (Out-of-Scope Detection)"),
    ("D3-P123_noprefill",   "P1-3",               r"+ Phase 3 (Principle Reasoning)"),
    ("D3-P1234_noprefill",  "P1-4",               r"+ Phase 4 (Category Labeling)"),
    ("D3-P1234_prefill",    "P1-4 + prefill",     r"+ Forced Prefix Pre-filling"),
]


def load_rate(csv_path: Path):
    if not csv_path.is_file():
        return None
    n = det = 0
    with csv_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            n += 1
            if (row.get("detected") or "").strip().lower() == "true":
                det += 1
    if n == 0:
        return None
    return {"n": n, "det": det, "rate": det / n * 100.0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True,
                    help="Directory containing the per-variant Finetune-RQ2 folders.")
    ap.add_argument("--out-csv", default="outputs/tab_phase_ablation.csv")
    ap.add_argument("--out-tex", default="outputs/tab_phase_ablation.tex")
    args = ap.parse_args()

    root = Path(args.root)
    out_csv = Path(args.out_csv)
    out_tex = Path(args.out_tex)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    # Aggregate
    rows = []
    prev_rate = 0.0
    for variant, label_short, label_long in ROW_LAYOUT:
        cell = load_rate(root / variant / "judge_summary.csv")
        if cell is None:
            rows.append({"variant": variant, "label": label_long, "status": "missing"})
            continue
        rows.append({
            "variant": variant,
            "label":   label_long,
            "status":  "ok",
            "n":       cell["n"],
            "det":     cell["det"],
            "rate":    cell["rate"],
            "delta":   cell["rate"] - prev_rate,
        })
        prev_rate = cell["rate"]

    # CSV
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["variant", "label", "detected", "n", "rate_pct", "delta_pp"])
        for r in rows:
            if r["status"] == "ok":
                w.writerow([r["variant"], r["label"],
                            r["det"], r["n"],
                            f"{r['rate']:.2f}", f"{r['delta']:+.2f}"])
            else:
                w.writerow([r["variant"], r["label"], "", "", "", ""])

    # LaTeX
    L = []
    L.append(r"\begin{table}[tb]")
    L.append(r"\centering")
    L.append(r"\caption{Four-phase schema ablation on Qwen2.5-Coder-7B-Instruct (paper Finding 3, $n=76$).}")
    L.append(r"\label{tab:finetune_rq2}")
    L.append(r"\begin{tabular}{lrrr}")
    L.append(r"\toprule")
    L.append(r"\textbf{Variant} & \textbf{Detected} & \textbf{Rate (\%)} & \textbf{$\Delta$pp} \\")
    L.append(r"\midrule")
    for r in rows:
        if r["status"] == "ok":
            L.append(rf"{r['label']} & {r['det']}/{r['n']} & {r['rate']:.2f} & {r['delta']:+.2f} \\")
        else:
            L.append(rf"{r['label']} & \textit{{missing}} & \textemdash & \textemdash \\")
    L.append(r"\bottomrule")
    L.append(r"\end{tabular}")
    L.append(r"\end{table}")
    out_tex.write_text("\n".join(L), encoding="utf-8")

    # Pretty print
    print(f"[saved] {out_csv}")
    print(f"[saved] {out_tex}\n")
    print(f"=== Finding 3: phase ablation (n=76) ===")
    print(f"{'Variant':<30}{'Det/n':>10}{'Rate':>10}{'Delta':>10}")
    print("-" * 60)
    for r in rows:
        if r["status"] == "ok":
            print(f"  {r['label']:<28}{r['det']}/{r['n']:<8}{r['rate']:>7.2f}%  {r['delta']:+7.2f}pp")
        else:
            print(f"  {r['label']:<28}(missing)")


if __name__ == "__main__":
    main()
