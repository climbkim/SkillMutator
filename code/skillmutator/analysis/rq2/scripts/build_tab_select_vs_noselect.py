"""build_tab_select_vs_noselect.py — Analysis 1 (select vs no-select),
oracle set by $SKILLMUTATOR_ORACLE (default gpt-5.4). Reads the unified data tree.

Each scanner's verdict per scenario = verdict at last_good_iter (carry-forward).
Denom: iter_0 normal scenarios. select n=76, no-select n=215.

Outputs:
  outputs/tab_select_vs_noselect.csv
"""
import csv, sys
from pathlib import Path
import sys

# Put the repo's `analysis/` directory on sys.path so `skillmutator_utils/`
# is importable regardless of the cwd this script is launched from.
_ANALYSIS_ROOT = Path(__file__).resolve().parents[2]
if str(_ANALYSIS_ROOT) not in sys.path:
    sys.path.insert(0, str(_ANALYSIS_ROOT))

import os
from skillmutator_utils.refusal import aggregate_scenario_final
from skillmutator_utils.paths import llm_scanners_for

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = Path("outputs/tab_select_vs_noselect.csv")

# Oracle is parametric: defaults to the paper's canonical gpt-5.4 oracle;
# override with $SKILLMUTATOR_ORACLE (e.g. run.sh sets it to the demo oracle).
ORACLE = os.environ.get("SKILLMUTATOR_ORACLE", "gpt-5.4")
SCANNERS = [("ss", "skill-security-scan"), ("snyk", "Snyk Agent Scan")]
for _s in llm_scanners_for(ORACLE):
    SCANNERS.append((f"llm/{_s}", f"{_s} scanner"))


def main():
    rows = []
    for sc_path, label in SCANNERS:
        sel = aggregate_scenario_final(ORACLE, "select", sc_path)
        nsl = aggregate_scenario_final(ORACLE, "no-select", sc_path)
        rows.append({
            "scanner": label, "scanner_path": sc_path,
            "n_select": sel["n"], "detected_select": sel["detected"],
            "rate_select_pct": f"{sel['rate_pct']:.2f}",
            "n_noselect": nsl["n"], "detected_noselect": nsl["detected"],
            "rate_noselect_pct": f"{nsl['rate_pct']:.2f}",
            "delta_pp": f"{nsl['rate_pct'] - sel['rate_pct']:+.2f}",
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows: w.writerow(r)

    avg_sel = sum(float(r["rate_select_pct"]) for r in rows) / len(rows)
    avg_nsl = sum(float(r["rate_noselect_pct"]) for r in rows) / len(rows)
    avg_dpp = avg_nsl - avg_sel

    print(f"[saved] {OUT}\n")
    print(f"=== select vs no-select ({ORACLE} oracle) ===")
    print(f"{'Scanner':<24} {'sel n':>6} {'sel %':>8} {'nsl n':>7} {'nsl %':>8} {'Δpp':>8}")
    print("-" * 70)
    for r in rows:
        print(f"  {r['scanner']:<22} {r['n_select']:>6} {r['rate_select_pct']:>8} "
              f"{r['n_noselect']:>7} {r['rate_noselect_pct']:>8} {r['delta_pp']:>8}")
    print("-" * 70)
    print(f"  {'Average (5 scanners)':<22} {'':>6} {avg_sel:>8.2f} {'':>7} {avg_nsl:>8.2f} {avg_dpp:>+8.2f}")


if __name__ == "__main__":
    main()
