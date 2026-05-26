"""Paper Table V (`tab:select_vs_noselect`) — Stealth-aware Attack Selection ablation.

Compares detection rate of the five primary scanners on the same 17 target
skills under two mutation modes:
  - `select`:    Stealth Score > 80 attack categories only (paper-canonical)
  - `no-select`: all 13 categories applied uniformly

Both modes use GPT-5.4 as the adversarial oracle and the GPT-5.4 judge.

Outputs:
  outputs/table5_select_vs_noselect.csv
  outputs/table5_select_vs_noselect.tex
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from lib.data_access import load_all_rows
from lib.refusal import aggregate_scenario_final

OUT = _ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

PRIMARY_SCANNERS = [
    ("ss",   "skill-security-scan"),
    ("snyk", "Snyk Agent Scan"),
    # The three proprietary LLM scanners adjudicated against the GPT-5.4
    # oracle dataset: GPT-4o-mini cross, GPT-5.4-mini cross, GPT-5.4 self.
    # For simplicity we report only the SELF pair here; the cross pairs
    # are produced by the broader cross-model aggregator.
    ("llm",  "GPT-5.4 (LLM, self)"),
]


def _agg(rows: list[dict]) -> dict[str, dict[str, int]]:
    """Aggregate per scanner using refusal-free re-pinning at K = 4."""
    agg = aggregate_scenario_final(rows, scanner_keys=("ss", "snyk", "llm"), k=4)
    out: dict[str, dict[str, int]] = {}
    for (oracle, _, sc), cell in agg.items():
        if oracle != "gpt-5.4":
            continue
        out[sc] = cell
    return out


def main() -> int:
    rows_select = load_all_rows(mode="select",   oracles=("gpt-5.4",))
    rows_noselect = load_all_rows(mode="no-select", oracles=("gpt-5.4",))

    agg_s  = _agg(rows_select)
    agg_ns = _agg(rows_noselect)

    csv_path = OUT / "table5_select_vs_noselect.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["scanner", "select_n", "select_det", "select_rate_pct",
                    "noselect_n", "noselect_det", "noselect_rate_pct",
                    "delta_pp"])
        for sc, label in PRIMARY_SCANNERS:
            cs = agg_s.get(sc) or {"n": 0, "det": 0}
            cn = agg_ns.get(sc) or {"n": 0, "det": 0}
            rs = 100.0 * cs["det"] / cs["n"] if cs["n"] else 0.0
            rn = 100.0 * cn["det"] / cn["n"] if cn["n"] else 0.0
            w.writerow([label, cs["n"], cs["det"], f"{rs:.2f}",
                        cn["n"], cn["det"], f"{rn:.2f}",
                        f"{rn - rs:+.2f}"])

    # LaTeX (compact form matching paper)
    L = []
    L.append(r"\begin{table}[t]")
    L.append(r"\centering")
    L.append(r"\caption{Detection rate (\%) for the \texttt{select} and \texttt{no-select} modes on the GPT-5.4 oracle dataset, adjudicated by GPT-5.4 judge.}")
    L.append(r"\label{tab:select_vs_noselect}")
    L.append(r"\resizebox{\columnwidth}{!}{")
    L.append(r"\begin{tabular}{lccc}")
    L.append(r"\toprule")
    L.append(r"\textbf{Scanner} & \textbf{\texttt{select}} & \textbf{\texttt{no-select}} & \textbf{$\Delta$} \\")
    L.append(r"\midrule")
    sum_s = sum_n = 0.0
    cnt = 0
    for sc, label in PRIMARY_SCANNERS:
        cs = agg_s.get(sc) or {"n": 0, "det": 0}
        cn = agg_ns.get(sc) or {"n": 0, "det": 0}
        rs = 100.0 * cs["det"] / cs["n"] if cs["n"] else 0.0
        rn = 100.0 * cn["det"] / cn["n"] if cn["n"] else 0.0
        sum_s += rs; sum_n += rn; cnt += 1
        L.append(rf"{label} & {rs:.2f}\% & {rn:.2f}\% & ${rn - rs:+.2f}$\,pp \\")
    avg_s = sum_s / cnt if cnt else 0.0
    avg_n = sum_n / cnt if cnt else 0.0
    L.append(r"\midrule")
    L.append(rf"\textbf{{Average ({cnt} scanners)}} & \textbf{{{avg_s:.2f}\%}} & \textbf{{{avg_n:.2f}\%}} & $\mathbf{{{avg_n - avg_s:+.2f}}}$\,pp \\")
    L.append(r"\bottomrule")
    L.append(r"\end{tabular}}")
    L.append(r"\end{table}")
    (OUT / "table5_select_vs_noselect.tex").write_text("\n".join(L), encoding="utf-8")

    print(f"[saved] {csv_path}")
    print(f"[saved] {OUT / 'table5_select_vs_noselect.tex'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
