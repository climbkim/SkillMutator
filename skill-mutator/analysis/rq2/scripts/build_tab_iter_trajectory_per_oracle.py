"""build_tab_iter_trajectory_per_oracle.py — Analysis 2 split into 3 oracle-
specific tables. Each table shows SS, Snyk, and the oracle's matched LLM
scanner across 5 iters (carry-forward, denom = iter_0 normal scenarios).

Outputs (one CSV per oracle + a pretty-printed combined view):
  outputs/tab_iter_trajectory_gpt-4o-mini.csv
  outputs/tab_iter_trajectory_gpt-5.4-mini.csv
  outputs/tab_iter_trajectory_gpt-5.4.csv
"""
import csv, sys
from pathlib import Path
import sys

# Put the repo's `analysis/` directory on sys.path so `skillmutator_utils/`
# is importable regardless of the cwd this script is launched from.
_ANALYSIS_ROOT = Path(__file__).resolve().parents[2]
if str(_ANALYSIS_ROOT) not in sys.path:
    sys.path.insert(0, str(_ANALYSIS_ROOT))

from skillmutator_utils.refusal import aggregate_per_iter
from skillmutator_utils.paths import ORACLES

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT_DIR = Path("outputs")

# Per-oracle scanner triple (3 scanners): SS, Snyk, oracle-self LLM
SCANNER_LABEL = {
    "ss":   "skill-security-scan",
    "snyk": "Snyk Agent Scan",
}


def matched_llm_for(oracle: str) -> tuple[str, str]:
    return f"llm/{oracle}-self", f"{oracle.upper().replace('GPT-','GPT-')} (self)"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"=== Analysis 2 — per-oracle iter trajectory (carry-forward) ===\n")
    for oracle in ORACLES:
        llm_path, llm_label = matched_llm_for(oracle)
        scanners = [
            ("ss",   "skill-security-scan"),
            ("snyk", "Snyk Agent Scan"),
            (llm_path, f"{oracle} scanner (self)"),
        ]
        rows_long = []
        n_at_iter0 = None
        for sc_path, label in scanners:
            iter_rows = aggregate_per_iter(oracle, "select", sc_path, rule="carry_forward")
            for r in iter_rows:
                if n_at_iter0 is None: n_at_iter0 = r["n"]
                rows_long.append({
                    "scanner": label, "scanner_path": sc_path,
                    "iter": r["iter"], "n": r["n"],
                    "detected": r["detected"],
                    "carried_forward": r["carried_forward"],
                    "rate_pct": f"{r['rate_pct']:.2f}",
                })

        # Save CSV
        csv_path = OUT_DIR / f"tab_iter_trajectory_{oracle}.csv"
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows_long[0].keys()))
            w.writeheader()
            for r in rows_long: w.writerow(r)
        print(f"[saved] {csv_path}")

        # Pretty print
        print(f"\n--- {oracle} dataset (n = {n_at_iter0}) ---")
        print(f"{'Scanner':<26}" + "".join(f"{f'iter_{i}':>13}" for i in range(5)))
        print("-" * (26 + 13*5))
        for sc_path, label in scanners:
            line = f"  {label:<24}"
            for it in range(5):
                row = next(r for r in rows_long if r["scanner_path"]==sc_path and r["iter"]==it)
                cell = f"{row['detected']:>2}/{row['n']:<2} {float(row['rate_pct']):>5.2f}%"
                line += f" {cell:>12}"
            print(line)
        print()


if __name__ == "__main__":
    main()
