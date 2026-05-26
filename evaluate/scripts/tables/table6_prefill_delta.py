"""Paper Table VI (`tab:prefill_delta_comparison`) — fine-tuned families
× prefill effect × cross-family Claude judge.

Aggregates per-(model, variant) judge_summary.csv files produced by the
skill-scanner-finetune evaluation pipeline. Variants:
  - base
  - D3-noprefill  (legacy on-disk tag; display label = "no-prefill")
  - D3-prefill    (display label = "prefill")

For each model × variant cell, two columns are reported: GPT-5.4 judge and
cross-family Claude Opus 4.7 judge. The Claude judge values come from
$FINETUNE_SCAN_ROOT/<model>_<variant>/judge_summary_claude.csv (parallel file).

Outputs:
  outputs/table6_prefill_delta.{csv,tex}
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

MODELS = [
    ("Qwen2.5-Coder-7B-Instruct",  "Qwen2.5-Coder-7B-Instruct"),
    ("Llama-3.1-8B-Instruct",      "Llama-3.1-8B-Instruct"),
    ("Mistral-7B-Instruct-v0.3",   "Mistral-7B-Instruct-v0.3"),
    ("Gemma-2-9b-it",              "Gemma-2-9b-it"),
]
VARIANTS = [
    ("base",         "Base"),
    ("D3-noprefill", "No-prefill"),
    ("D3-prefill",   "Prefill"),
]
JUDGES = [
    ("judge_summary.csv",        "GPT-5.4 Judge"),
    ("judge_summary_claude.csv", "Claude Judge"),
]


def _scan_root() -> Path:
    p = os.environ.get("FINETUNE_SCAN_ROOT")
    if not p:
        raise RuntimeError(
            "FINETUNE_SCAN_ROOT not set. Export it to the dir containing "
            "<model>_<variant>/judge_summary.csv files."
        )
    return Path(p)


def load_cell(scan_root: Path, model_dir: str, variant: str, judge_file: str) -> dict | None:
    p = scan_root / f"{model_dir}_{variant}" / judge_file
    if not p.is_file():
        return None
    n = det = 0
    with p.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            n += 1
            if str(r.get("detected", "")).strip().lower() == "true":
                det += 1
    return {"n": n, "det": det, "rate": 100.0 * det / n if n else 0.0}


def main() -> int:
    scan_root = _scan_root()
    table = {}
    for m_dir, m_label in MODELS:
        for v_key, v_label in VARIANTS:
            for j_file, j_label in JUDGES:
                cell = load_cell(scan_root, m_dir, v_key, j_file)
                table[(m_label, v_label, j_label)] = cell

    # CSV
    csv_path = OUT / "table6_prefill_delta.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["model", "variant", "judge", "n", "detected", "rate_pct"])
        for m_dir, m_label in MODELS:
            for v_key, v_label in VARIANTS:
                for j_file, j_label in JUDGES:
                    c = table.get((m_label, v_label, j_label))
                    if c is None:
                        w.writerow([m_label, v_label, j_label, "", "", ""])
                    else:
                        w.writerow([m_label, v_label, j_label, c["n"], c["det"], f"{c['rate']:.2f}"])

    # LaTeX (compact form mirroring paper layout)
    L = []
    L.append(r"\begin{table*}[t]")
    L.append(r"\centering")
    L.append(r"\caption{Detection rate (\%) of base and fine-tuned models, with the frontier GPT-5.4 LLM as a self-detection reference row. $\Delta$ = prefill $-$ no-prefill measures the effect of Phase~4 header prefill.}")
    L.append(r"\label{tab:prefill_delta_comparison}")
    L.append(r"\resizebox{\textwidth}{!}{")
    L.append(r"\begin{tabular}{lrrrrrrrr}")
    L.append(r"\toprule")
    L.append(r"\multirow{2}{*}{\textbf{Model}} & \multicolumn{4}{c}{\textbf{GPT-5.4 Judge}} & \multicolumn{4}{c}{\textbf{Claude Judge}} \\")
    L.append(r"\cmidrule(lr){2-5} \cmidrule(l){6-9}")
    L.append(r" & \textbf{Base} & \textbf{no-prefill} & \textbf{prefill} & \textbf{$\Delta$} "
             r"& \textbf{Base} & \textbf{no-prefill} & \textbf{prefill} & \textbf{$\Delta$} \\")
    L.append(r"\midrule")
    for m_dir, m_label in MODELS:
        cells = []
        for j_file, j_label in JUDGES:
            for v_key, v_label in VARIANTS:
                c = table.get((m_label, v_label, j_label))
                cells.append(f"{c['rate']:.1f}\\%" if c else r"\textemdash")
            cb = table.get((m_label, "Base", j_label))
            cn = table.get((m_label, "No-prefill", j_label))
            cp = table.get((m_label, "Prefill", j_label))
            if cn and cp:
                cells.append(f"${cp['rate'] - cn['rate']:+.1f}$\\,pp")
            else:
                cells.append(r"\textemdash")
        L.append(rf"{m_label} & " + " & ".join(cells) + r" \\")
    L.append(r"\bottomrule")
    L.append(r"\end{tabular}}")
    L.append(r"\end{table*}")
    (OUT / "table6_prefill_delta.tex").write_text("\n".join(L), encoding="utf-8")

    print(f"[saved] {csv_path}")
    print(f"[saved] {OUT / 'table6_prefill_delta.tex'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
