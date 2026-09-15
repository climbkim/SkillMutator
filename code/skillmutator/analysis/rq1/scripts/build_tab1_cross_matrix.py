"""build_tab1_cross_matrix.py — paper Table IV (cross-scanner detection
rate matrix). Reads from the unified Skillmutator-data tree.

Per (oracle, scanner) cell:
  - denom = `all_attempted`   (n = 51 / 63 / 76, matches paper)
  - verdict per scenario      = at last_good_iter; missing/never-good → False
  - rate                      = detected / n × 100

Outputs:
  outputs/tab1_cross_matrix.csv
  outputs/tab1_cross_matrix.tex
"""
import csv, sys
from pathlib import Path

# Put the repo's `analysis/` directory on sys.path so `skillmutator_utils/`
# is importable regardless of the cwd this script is launched from.
_ANALYSIS_ROOT = Path(__file__).resolve().parents[2]
if str(_ANALYSIS_ROOT) not in sys.path:
    sys.path.insert(0, str(_ANALYSIS_ROOT))

from skillmutator_utils.refusal import aggregate_scenario_final, valid_scenarios
from skillmutator_utils.paths import ORACLES

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT_CSV = Path("outputs/tab1_cross_matrix.csv")
OUT_TEX = Path("outputs/tab1_cross_matrix.tex")

# Display row order (paper-aligned)
ROW_LAYOUT = [
    ("section", "Rule-based / Commercial"),
    ("scanner", "ss",                   r"\texttt{skill-security-scan}"),
    ("scanner", "snyk",                 "Snyk Agent Scan"),
    ("section", "Proprietary LLM Scanners"),
    ("scanner", "gpt-4o-mini",          "GPT-4o-mini"),
    ("scanner", "gpt-5.4-mini",         "GPT-5.4-mini"),
    ("scanner", "gpt-5.4",              "GPT-5.4"),
]

DENOM = "all_attempted"


def _scanner_subpath(scanner: str, oracle: str) -> str:
    """Resolve display-row scanner name to its tree subpath for a given oracle."""
    if scanner in ("ss", "snyk"):
        return scanner
    # LLM scanner — diagonal uses '<oracle>-self', off-diagonal uses '<scanner>'
    return f"llm/{scanner}-self" if scanner == oracle else f"llm/{scanner}"


def main():
    n_per_oracle = {o: len(valid_scenarios(o, "select", criterion=DENOM)) for o in ORACLES}

    rows = []
    for kind, *info in ROW_LAYOUT:
        if kind == "section":
            rows.append({"_section": info[0]})
            continue
        sc_key, label = info
        row = {"scanner": label, "scanner_key": sc_key}
        for oracle in ORACLES:
            sub = _scanner_subpath(sc_key, oracle)
            r = aggregate_scenario_final(oracle, "select", sub, denom=DENOM)
            row[f"{oracle}_n"]    = r["n"]
            row[f"{oracle}_det"]  = r["detected"]
            row[f"{oracle}_rate"] = r["rate_pct"]
        rows.append(row)

    # CSV
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fields = ["scanner","scanner_key"]
    for o in ORACLES:
        fields += [f"{o}_n", f"{o}_det", f"{o}_rate"]
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            if "_section" in r: continue
            w.writerow(r)

    # LaTeX (paper-shaped)
    def fmt(rate: float, bold: bool=False) -> str:
        s = f"{rate:.2f}"
        return f"\\textbf{{{s}}}" if bold else s

    # Identify per-oracle max LLM rate for bolding
    llm_keys = [r.get("scanner_key") for r in rows if r.get("scanner_key") in ("gpt-4o-mini","gpt-5.4-mini","gpt-5.4")]
    max_per_oracle = {o: max((r[f"{o}_rate"] for r in rows if r.get("scanner_key") in llm_keys), default=0)
                      for o in ORACLES}

    L = []
    L.append(r"\begin{table}[tb]")
    L.append(r"\centering")
    L.append(r"\caption{Detection rate (\%) across three adversarial oracle datasets.")
    L.append(r"LLM-scanner outputs are adjudicated by a single GPT-5.4 judge (\S\ref{sec:judge}).")
    L.append(r"Eval $n$ recovers baseline-identical scenarios via earlier-iter normal mutations,")
    L.append(r"so $n$ matches the attempted-scenario count for each oracle.}")
    L.append(r"\label{tab:cross_matrix}")
    L.append(r"\footnotesize")
    L.append(r"\setlength{\tabcolsep}{3pt}")
    L.append(r"\resizebox{\columnwidth}{!}{%")
    L.append(r"\begin{tabular}{lrrr}")
    L.append(r"\toprule")
    L.append(r"\multirow{2}{*}{\textbf{Scanner}} & \multicolumn{3}{c}{\textbf{Adversarial Oracle Dataset}} \\")
    L.append(r"\cmidrule(lr){2-4}")
    L.append(r" & GPT-4o-mini & GPT-5.4-mini & GPT-5.4 \\")
    L.append(r"\midrule")
    L.append(r"\textit{Eval samples} ($n$) & "
             f"{n_per_oracle['gpt-4o-mini']} & "
             f"{n_per_oracle['gpt-5.4-mini']} & "
             f"{n_per_oracle['gpt-5.4']} \\\\")
    L.append(r"\midrule")
    for r in rows:
        if "_section" in r:
            L.append(rf"\multicolumn{{4}}{{l}}{{\textit{{{r['_section']}}}}} \\")
            continue
        cells = []
        for o in ORACLES:
            rate = r[f"{o}_rate"]
            bold = (r.get("scanner_key") in ("gpt-4o-mini","gpt-5.4-mini","gpt-5.4")
                    and abs(rate - max_per_oracle[o]) < 1e-6)
            cells.append(fmt(rate, bold=bold))
        L.append(rf"{r['scanner']:<32} & {cells[0]:>10} & {cells[1]:>10} & {cells[2]:>10} \\")
    L.append(r"\bottomrule")
    L.append(r"\end{tabular}%")
    L.append(r"}")
    L.append(r"\end{table}")
    OUT_TEX.write_text("\n".join(L), encoding="utf-8")

    # Pretty print
    print(f"[saved] {OUT_CSV}")
    print(f"[saved] {OUT_TEX}\n")
    print(f"=== Table 1: Detection rate (%) — denom={DENOM}, scenario-final (last_good_iter) ===")
    print(f"{'':<32}" + "".join(f"{o:>22}" for o in ORACLES))
    print(f"{'Eval samples (n)':<32}" + "".join(f"{n_per_oracle[o]:>22}" for o in ORACLES))
    print("-" * 100)
    for r in rows:
        if "_section" in r:
            print(f"  [{r['_section']}]"); continue
        line = f"  {r['scanner']:<30}"
        for o in ORACLES:
            cell = f"{r[f'{o}_det']}/{r[f'{o}_n']}={r[f'{o}_rate']:>5.2f}%"
            line += f"{cell:>22}"
        print(line)


if __name__ == "__main__":
    main()
