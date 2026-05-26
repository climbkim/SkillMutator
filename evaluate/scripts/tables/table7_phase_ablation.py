"""Paper Table VII (`tab:finetune_rq2`) — four-phase schema ablation on
Qwen2.5-Coder-7B-Instruct.

Cumulative ablation: train on Phase 1 only, then Phase 1+2, then 1+2+3, then
1+2+3+4, then add deterministic refine, then add forced Phase 4 prefill.

Expected input layout under $FINETUNE_SCAN_ROOT:
  <root>/D3-P1_noprefill/judge_summary.csv
  <root>/D3-P12_noprefill/judge_summary.csv
  <root>/D3-P123_noprefill/judge_summary.csv
  <root>/D3-P1234_noprefill/judge_summary.csv
  <root>/D3-P1234_refine/judge_summary.csv
  <root>/D3-P1234_prefill/judge_summary.csv

The `D3-` prefix is the legacy on-disk data tag retained for backward
compatibility; the LaTeX output uses paper-facing display labels (Phase 1
Purpose Grounding, etc.).

Outputs:
  outputs/table7_phase_ablation.{csv,tex}
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

OUT = _ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

ROWS = [
    # (on-disk variant suffix, paper-facing display label)
    ("D3-P1_noprefill",     r"Phase 1 (Purpose Grounding)"),
    ("D3-P12_noprefill",    r"+ Phase 2 (Out-of-Scope Detection)"),
    ("D3-P123_noprefill",   r"+ Phase 3 (Principle Reasoning)"),
    ("D3-P1234_noprefill",  r"+ Phase 4 (Category Labeling)"),
    ("D3-P1234_refine",     r"\;\;{\small + deterministic refine}"),
    ("D3-P1234_prefill",    r"\;\;{\small + prefill (Phase 4 header forced)}"),
]


def _scan_root() -> Path:
    p = os.environ.get("FINETUNE_SCAN_ROOT")
    if not p:
        raise RuntimeError("FINETUNE_SCAN_ROOT not set.")
    return Path(p)


def load_rate(csv_path: Path) -> dict | None:
    if not csv_path.is_file():
        return None
    n = det = 0
    with csv_path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            n += 1
            if str(r.get("detected", "")).strip().lower() == "true":
                det += 1
    return {"n": n, "det": det, "rate": 100.0 * det / n if n else 0.0}


def main() -> int:
    root = _scan_root()
    rows = []
    prev = 0.0
    for variant, label in ROWS:
        cell = load_rate(root / variant / "judge_summary.csv")
        if cell is None:
            rows.append({"variant": variant, "label": label, "status": "missing"})
            continue
        rows.append({
            "variant": variant,
            "label": label,
            "status": "ok",
            "n": cell["n"],
            "det": cell["det"],
            "rate": cell["rate"],
            "delta": cell["rate"] - prev,
        })
        prev = cell["rate"]

    csv_path = OUT / "table7_phase_ablation.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["variant", "label", "n", "detected", "rate_pct", "delta_pp"])
        for r in rows:
            if r["status"] == "ok":
                w.writerow([r["variant"], r["label"], r["n"], r["det"],
                            f"{r['rate']:.2f}", f"{r['delta']:+.2f}"])
            else:
                w.writerow([r["variant"], r["label"], "", "", "", ""])

    # LaTeX
    L = []
    L.append(r"\begin{table}[t]")
    L.append(r"\centering")
    L.append(r"\caption{Four-phase schema ablation on Qwen2.5-Coder-7B-Instruct.}")
    L.append(r"\label{tab:finetune_rq2}")
    L.append(r"\resizebox{\columnwidth}{!}{")
    L.append(r"\begin{tabular}{lrr}")
    L.append(r"\toprule")
    L.append(r"\textbf{Schema} & \textbf{Detection Rate} & \textbf{$\Delta$} \\")
    L.append(r"\midrule")
    for i, r in enumerate(rows):
        if r["status"] == "ok":
            delta = "---" if i == 0 else f"$+{r['delta']:.1f}\\text{{\\,pp}}$"
            L.append(rf"{r['label']} & {r['rate']:.2f}\% & {delta} \\")
        else:
            L.append(rf"{r['label']} & \textit{{missing}} & \textemdash \\")
    L.append(r"\bottomrule")
    L.append(r"\end{tabular}}")
    L.append(r"\end{table}")
    (OUT / "table7_phase_ablation.tex").write_text("\n".join(L), encoding="utf-8")

    print(f"[saved] {csv_path}")
    print(f"[saved] {OUT / 'table7_phase_ablation.tex'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
