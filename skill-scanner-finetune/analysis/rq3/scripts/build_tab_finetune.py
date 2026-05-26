"""build_tab_finetune.py — Finetune-RQ1 paper table.

Aggregates per-folder judge_summary.csv into a 4-model x 3-variant detection
rate matrix. Reads from ../<Model>_<variant>/judge_summary.csv.

Excluded:
  - Llama-3.1-8B-Instruct_base (denominator 65/76, scan incomplete)
  - Yi-Coder-9B-Chat (all 3 variants pending v3 truncate rerun)

Outputs:
  outputs/tab_finetune.csv      one row per (model, variant) cell
  outputs/tab_finetune.tex      paper-shaped LaTeX
  outputs/tab_finetune_by_cat.csv  per-category detection per cell
"""
import csv, sys
from pathlib import Path
from collections import defaultdict

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT     = Path("..")
OUT_CSV  = ROOT / "outputs" / "tab_finetune.csv"
OUT_TEX  = ROOT / "outputs" / "tab_finetune.tex"
OUT_CAT  = ROOT / "outputs" / "tab_finetune_by_cat.csv"

MODELS = [
    ("Qwen2.5-Coder-7B-Instruct", "Qwen2.5-Coder-7B-Instruct"),
    ("Llama-3.1-8B-Instruct",     "Llama-3.1-8B-Instruct"),
    ("Mistral-7B-Instruct-v0.3",  "Mistral-7B-Instruct-v0.3"),
    ("Gemma-2-9b-it",             "Gemma-2-9b-it"),
]
VARIANTS = [("base", "Base"), ("D3-noprefill", "No-prefill"), ("D3-prefill", "Prefill")]
# Note: the first tuple element is the on-disk data directory suffix and is
# retained as-is to remain compatible with the existing judge_summary.csv
# layout; the second tuple element is the paper-facing display label.

# Cells excluded from the headline table
SKIP = {("Llama-3.1-8B-Instruct", "base")}


def load_cell(model_dir: str, variant: str):
    csv_p = ROOT / f"{model_dir}_{variant}" / "judge_summary.csv"
    if not csv_p.is_file():
        return None
    n = det = 0
    by_cat = defaultdict(lambda: [0, 0])  # cat -> [det, n]
    with open(csv_p, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            n += 1
            d = row["detected"].strip().lower() == "true"
            if d: det += 1
            c = row.get("cat_folder", "") or row.get("category", "")
            by_cat[c][1] += 1
            if d: by_cat[c][0] += 1
    return {"n": n, "det": det, "rate": det / n * 100 if n else 0.0, "by_cat": dict(by_cat)}


def main():
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for model_dir, label in MODELS:
        for v_key, v_label in VARIANTS:
            if (model_dir, v_key) in SKIP:
                rows.append({"model": label, "variant": v_label, "status": "excluded"})
                continue
            c = load_cell(model_dir, v_key)
            if c is None:
                rows.append({"model": label, "variant": v_label, "status": "pending"})
                continue
            rows.append({"model": label, "variant": v_label, "status": "ok",
                         "n": c["n"], "det": c["det"], "rate": c["rate"]})

    # Main CSV
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["model", "variant", "status", "detected", "n", "rate_pct"])
        for r in rows:
            w.writerow([r["model"], r["variant"], r["status"],
                        r.get("det", ""), r.get("n", ""),
                        f"{r['rate']:.2f}" if r["status"] == "ok" else ""])

    # Per-category CSV
    cells = {}
    for model_dir, label in MODELS:
        for v_key, v_label in VARIANTS:
            if (model_dir, v_key) in SKIP: continue
            c = load_cell(model_dir, v_key)
            if c is None: continue
            cells[(label, v_label)] = c
    cats = sorted({c for cell in cells.values() for c in cell["by_cat"]})
    with open(OUT_CAT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["model", "variant", "category", "detected", "n", "rate_pct"])
        for (m, v), cell in cells.items():
            for c in cats:
                d, n = cell["by_cat"].get(c, [0, 0])
                if n == 0: continue
                w.writerow([m, v, c, d, n, f"{d/n*100:.2f}"])

    # LaTeX
    L = []
    L.append(r"\begin{table}[tb]")
    L.append(r"\centering")
    L.append(r"\caption{Detection rate (\%) of base models vs.\ fine-tuned variants on the 76-case SkillMutator benchmark (GPT-5.4 judge).}")
    L.append(r"\label{tab:finetune_rq2}")
    L.append(r"\footnotesize")
    L.append(r"\setlength{\tabcolsep}{4pt}")
    L.append(r"\begin{tabular}{lrrr}")
    L.append(r"\toprule")
    L.append(r"\textbf{Model} & \textbf{Base} & \textbf{No-prefill} & \textbf{Prefill} \\")
    L.append(r"\midrule")
    # Compute per-row max for bolding the fine-tuned columns
    by_model = defaultdict(dict)
    for r in rows:
        by_model[r["model"]][r["variant"]] = r
    for _, label in MODELS:
        line_cells = []
        ft_rates = [by_model[label].get(v, {}).get("rate") for v in ("No-prefill", "Prefill")]
        ft_rates = [x for x in ft_rates if x is not None]
        ft_max = max(ft_rates) if ft_rates else None
        for _, v_label in VARIANTS:
            r = by_model[label].get(v_label, {})
            st = r.get("status")
            if st == "excluded":
                line_cells.append(r"\textemdash")
            elif st == "ok":
                s = f"{r['det']}/{r['n']} ({r['rate']:.1f})"
                if v_label != "Base" and ft_max is not None and abs(r["rate"] - ft_max) < 1e-6:
                    s = r"\textbf{" + s + "}"
                line_cells.append(s)
            else:
                line_cells.append(r"\textit{pending}")
        L.append(rf"{label} & " + " & ".join(line_cells) + r" \\")
    L.append(r"\bottomrule")
    L.append(r"\end{tabular}")
    L.append(r"\end{table}")
    OUT_TEX.write_text("\n".join(L), encoding="utf-8")

    # Pretty print
    print(f"[saved] {OUT_CSV}")
    print(f"[saved] {OUT_TEX}")
    print(f"[saved] {OUT_CAT}\n")
    print(f"=== Finetune-RQ1: detection rate (%) on 76-case benchmark, gpt-5.4 judge ===\n")
    print(f"{'Model':<32}" + "".join(f"{v_label:>22}" for _, v_label in VARIANTS))
    print("-" * 100)
    for _, label in MODELS:
        line = f"{label:<32}"
        for _, v_label in VARIANTS:
            r = by_model[label].get(v_label, {})
            st = r.get("status")
            if st == "ok":
                cell = f"{r['det']}/{r['n']} = {r['rate']:.2f}%"
            elif st == "excluded":
                cell = "(excluded)"
            else:
                cell = "(pending)"
            line += f"{cell:>22}"
        print(line)


if __name__ == "__main__":
    main()
