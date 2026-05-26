"""Paper Table IV (`tab:refusal_i4_summary`) — safety-refusal counts per oracle.

Reads `meta.json:classification` across the unified Skillmutator-data tree
and aggregates:
  - Attempted scenarios (n)
  - Refusal rate at final iteration
  - Refusals per iter (0/1/2/3/4)
  - Refusal mechanism breakdown (silent_failure / explicit_refusal / partial_refusal)

Outputs:
  outputs/table4_refusal_summary.csv
  outputs/table4_refusal_summary.tex
"""
from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from lib.data_access import ORACLES, load_all_rows

OUT = _ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

ORACLES_PLUS_CLAUDE = list(ORACLES) + ["claude-opus-4-7"]
ORACLE_LABELS = {
    "gpt-4o-mini":     "GPT-4o-mini",
    "gpt-5.4-mini":    "GPT-5.4-mini",
    "gpt-5.4":         "GPT-5.4",
    "claude-opus-4-7": "Claude-Opus-4.7",
}

REFUSAL_LABELS = ("silent_failure", "explicit_refusal", "partial_refusal", "missing")


def main() -> int:
    # Walk all 4 oracles (Claude only optional).
    rows = load_all_rows(mode="select", oracles=tuple(ORACLES_PLUS_CLAUDE))

    # Per (oracle, scenario, iter)
    by_scen: dict[tuple[str, str, str], dict[int, str | None]] = {}
    for r in rows:
        by_scen.setdefault((r["oracle"], r["skill"], r["category"]), {})[r["iter"]] = r["classification"]

    attempted = Counter()
    final_refusal = Counter()
    per_iter = {o: Counter() for o in ORACLES_PLUS_CLAUDE}
    mechanism = {o: Counter() for o in ORACLES_PLUS_CLAUDE}

    for (oracle, _, _), classifs in by_scen.items():
        attempted[oracle] += 1
        # Find final iter (largest available)
        if not classifs:
            continue
        final_k = max(classifs.keys())
        final_c = classifs[final_k]
        if final_c and final_c != "normal":
            final_refusal[oracle] += 1
            if final_c in REFUSAL_LABELS:
                mechanism[oracle][final_c] += 1
        for it, c in classifs.items():
            if c and c != "normal":
                per_iter[oracle][it] += 1

    # Write CSV
    csv_path = OUT / "table4_refusal_summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["oracle", "attempted_n",
                    "final_refusal_n", "final_refusal_rate_pct",
                    "refusals_per_iter_0", "refusals_per_iter_1",
                    "refusals_per_iter_2", "refusals_per_iter_3",
                    "refusals_per_iter_4",
                    "silent_failure_n", "explicit_refusal_n", "partial_refusal_n"])
        for o in ORACLES_PLUS_CLAUDE:
            n = attempted[o]
            r = final_refusal[o]
            rate = 100.0 * r / n if n else 0.0
            w.writerow([o, n, r, f"{rate:.2f}",
                        per_iter[o][0], per_iter[o][1], per_iter[o][2],
                        per_iter[o][3], per_iter[o][4],
                        mechanism[o]["silent_failure"],
                        mechanism[o]["explicit_refusal"],
                        mechanism[o]["partial_refusal"]])

    # LaTeX
    L = []
    L.append(r"\begin{table}[t]")
    L.append(r"\centering")
    L.append(r"\caption{Safety-refusal counts by adversarial oracle. When the final refinement iteration is a refusal, evaluation uses the most recent non-refusal mutation.}")
    L.append(r"\label{tab:refusal_i4_summary}")
    L.append(r"\resizebox{\columnwidth}{!}{")
    L.append(r"\begin{tabular}{l" + "r" * len(ORACLES_PLUS_CLAUDE) + "}")
    L.append(r"\toprule")
    L.append(r"\textbf{Metric} & "
             + " & ".join(rf"\textbf{{{ORACLE_LABELS[o]}}}" for o in ORACLES_PLUS_CLAUDE)
             + r" \\")
    L.append(r"\midrule")
    L.append(r"Attempted scenarios ($n$) & "
             + " & ".join(str(attempted[o]) for o in ORACLES_PLUS_CLAUDE) + r" \\")
    L.append(r"Refusal rate at final iteration & "
             + " & ".join(f"{100.0 * final_refusal[o] / attempted[o]:.2f}\\%" if attempted[o] else r"\textemdash"
                          for o in ORACLES_PLUS_CLAUDE) + r" \\")
    L.append(r"Refusals per iter ($n$) & "
             + " & ".join("/".join(str(per_iter[o][i]) for i in range(5)) for o in ORACLES_PLUS_CLAUDE)
             + r" \\")
    L.append(r"\midrule")
    L.append(r"\multicolumn{" + str(len(ORACLES_PLUS_CLAUDE) + 1) + r"}{l}{\textit{Refusal mechanism ($n$)}} \\")
    for mech in ("silent_failure", "explicit_refusal", "partial_refusal"):
        nice = mech.replace("_", " ").capitalize()
        L.append(rf"\;\;{nice} & "
                 + " & ".join(str(mechanism[o][mech]) for o in ORACLES_PLUS_CLAUDE) + r" \\")
    L.append(r"\bottomrule")
    L.append(r"\end{tabular}}")
    L.append(r"\end{table}")
    (OUT / "table4_refusal_summary.tex").write_text("\n".join(L), encoding="utf-8")

    print(f"[saved] {csv_path}")
    print(f"[saved] {OUT / 'table4_refusal_summary.tex'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
