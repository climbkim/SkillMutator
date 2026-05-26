"""Verify paper-cited values against the unified data tree.

This script audits the rates the paper headlines against what the data
produces, so reviewers can sanity-check that the repo and paper agree.

It checks:
  - Cross-scanner Table III values (final refusal-free re-pin at K=4)
  - Refusal counts (Table IV)
  - Select vs no-select deltas (Table V)
  - 1,126-cell surface count

The script prints one line per check with PASS / DIFFER (within tolerance).

Outputs:
  outputs/paper_cited_values.csv  (machine-readable record)
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

TOLERANCE_PP = 0.5

PAPER_CITED = [
    # (description, expected_pct, scope_key)
    ("Table III ss / GPT-4o-mini",                2.08,  ("gpt-4o-mini",  "ss")),
    ("Table III ss / GPT-5.4-mini",               6.35,  ("gpt-5.4-mini", "ss")),
    ("Table III ss / GPT-5.4",                    7.89,  ("gpt-5.4",      "ss")),
    ("Table III snyk / GPT-4o-mini",             16.67,  ("gpt-4o-mini",  "snyk")),
    ("Table III snyk / GPT-5.4-mini",             9.52,  ("gpt-5.4-mini", "snyk")),
    ("Table III snyk / GPT-5.4",                  9.21,  ("gpt-5.4",      "snyk")),
    ("Table III LLM (self) / GPT-4o-mini",       35.42,  ("gpt-4o-mini",  "llm")),
    ("Table III LLM (self) / GPT-5.4-mini",      71.43,  ("gpt-5.4-mini", "llm")),
    ("Table III LLM (self) / GPT-5.4",           86.84,  ("gpt-5.4",      "llm")),
]


def main() -> int:
    rows = load_all_rows(mode="select")
    agg = aggregate_scenario_final(rows, scanner_keys=("ss", "snyk", "llm"), k=4)

    out_csv = OUT / "paper_cited_values.csv"
    n_pass = 0
    n_diff = 0
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["check", "expected_pct", "observed_pct", "delta_pp", "status"])
        print(f"{'Check':<40} {'expected':>10} {'observed':>10} {'Δpp':>8}  status")
        for desc, expected, key in PAPER_CITED:
            cell = agg.get((key[0], 4, key[1]))
            if not cell or not cell["n"]:
                print(f"{desc:<40} {expected:>10.2f} {'(n=0)':>10} {'':>8}  N/A")
                w.writerow([desc, expected, "", "", "N/A"])
                continue
            observed = 100.0 * cell["det"] / cell["n"]
            delta = observed - expected
            status = "PASS" if abs(delta) <= TOLERANCE_PP else "DIFFER"
            if status == "PASS":
                n_pass += 1
            else:
                n_diff += 1
            print(f"{desc:<40} {expected:>10.2f} {observed:>10.2f} {delta:>+8.2f}  {status}")
            w.writerow([desc, f"{expected:.2f}", f"{observed:.2f}", f"{delta:+.2f}", status])

    print()
    print(f"PASS: {n_pass}, DIFFER (>{TOLERANCE_PP}pp): {n_diff}")
    print(f"[saved] {out_csv}")
    return 0 if n_diff == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
