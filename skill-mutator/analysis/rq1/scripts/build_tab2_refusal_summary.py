"""build_tab2_refusal_summary.py — paper Table III: refusal summary per (oracle, mode).
Uses the unified classifications module (which builds from raw mutation JSONs).
"""
import csv, sys
from pathlib import Path
import sys

# Put the repo's `analysis/` directory on sys.path so `skillmutator_utils/`
# is importable regardless of the cwd this script is launched from.
_ANALYSIS_ROOT = Path(__file__).resolve().parents[2]
if str(_ANALYSIS_ROOT) not in sys.path:
    sys.path.insert(0, str(_ANALYSIS_ROOT))

from skillmutator_utils.refusal import refusal_summary, per_iter_classification_counts
from skillmutator_utils.paths import ORACLES, MODES_BY_ORACLE

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT_SUMMARY  = Path("outputs/tab2_refusal_summary.csv")
OUT_PER_ITER = Path("outputs/tab2_refusal_per_iter.csv")


def main():
    rows = []
    per_iter_rows = []
    for o in ORACLES:
        for m in MODES_BY_ORACLE[o]:
            s = refusal_summary(o, m)
            rows.append(s)
            counts = per_iter_classification_counts(o, m)
            for it, dist in counts.items():
                per_iter_rows.append({
                    "oracle": o, "mode": m, "iter": it,
                    "normal":           dist.get("normal", 0),
                    "explicit_refusal": dist.get("explicit_refusal", 0),
                    "silent_failure":   dist.get("silent_failure", 0),
                    "partial_refusal":  dist.get("partial_refusal", 0),
                    "total":            sum(dist.values()),
                })

    OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    with open(OUT_SUMMARY, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for r in rows: w.writerow(r)
    with open(OUT_PER_ITER, "w", encoding="utf-8", newline="") as f:
        if per_iter_rows:
            w = csv.DictWriter(f, fieldnames=list(per_iter_rows[0].keys())); w.writeheader()
            for _r in per_iter_rows: w.writerow(_r)
        for r in per_iter_rows: w.writerow(r)

    print(f"[saved] {OUT_SUMMARY}")
    print(f"[saved] {OUT_PER_ITER}\n")
    print(f"=== Refusal summary (scenario-final classification) ===")
    print(f"{'oracle/mode':<22} {'total':>6} {'normal':>7} {'explicit':>9} {'silent':>7} {'partial':>8} {'rate %':>8}")
    print("-" * 75)
    for r in rows:
        print(f"  {r['oracle']}/{r['mode']:<14} {r['total_scenarios']:>6} {r['normal']:>7} "
              f"{r['explicit_refusal']:>9} {r['silent_failure']:>7} {r['partial_refusal']:>8} "
              f"{r['any_refusal_rate_pct']:>8.2f}")


if __name__ == "__main__":
    main()
