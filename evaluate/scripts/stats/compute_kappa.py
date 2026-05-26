"""Cohen's $\\kappa$ between the GPT-5.4 judge and the cross-family Claude
Opus 4.7 judge on the 1,126-cell evaluation surface (paper §7 Limitations 3).

For each scanner/model-mode combination (15 in total), computes:
  - n: cells with both judge verdicts
  - GPT detection count, Claude detection count
  - Cohen's kappa
  - agreement %

Expected inputs:
  - $JUDGE_GPT_ROOT/<combination>/verdicts.csv  (columns: skill, category, iter, detected)
  - $JUDGE_CLAUDE_ROOT/<combination>/verdicts.csv

Outputs:
  outputs/kappa_summary.csv
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

# 15 scanner / model-mode combinations (paper §7 Limitations 3)
COMBINATIONS = [
    "gpt-4o-mini-self",
    "gpt-5.4-mini-self",
    "gpt-5.4-self",
    "qwen-base",
    "qwen-d3-noprefill",
    "qwen-d3-prefill",
    "llama-base",
    "llama-d3-noprefill",
    "llama-d3-prefill",
    "mistral-base",
    "mistral-d3-noprefill",
    "mistral-d3-prefill",
    "gemma-base",
    "gemma-d3-noprefill",
    "gemma-d3-prefill",
]


def cohens_kappa(p_a: int, p_b: int, n: int, both: int) -> float:
    """Cohen's kappa for binary 2x2 table.

    Args:
      p_a: count where judge A = True
      p_b: count where judge B = True
      n:   total paired cells
      both: count where both A=True AND B=True

    Note: agreement = both (T,T) + (n - p_a - p_b + both) (F,F).
    """
    if n == 0:
        return 0.0
    agree_tt = both
    agree_ff = n - p_a - p_b + both
    po = (agree_tt + agree_ff) / n
    pyes = (p_a * p_b) / (n * n)
    pno  = ((n - p_a) * (n - p_b)) / (n * n)
    pe = pyes + pno
    if abs(1 - pe) < 1e-12:
        return 1.0 if po > 1 - 1e-12 else 0.0
    return (po - pe) / (1 - pe)


def load_verdicts(d: Path) -> dict[tuple, bool]:
    """key = (skill, category, iter) -> detected bool."""
    if not d.is_dir():
        return {}
    out: dict[tuple, bool] = {}
    p = d / "verdicts.csv"
    if not p.is_file():
        return out
    with p.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            key = (r["skill"], r["category"], int(r["iter"]))
            out[key] = str(r["detected"]).strip().lower() == "true"
    return out


def main() -> int:
    gpt_root = os.environ.get("JUDGE_GPT_ROOT")
    claude_root = os.environ.get("JUDGE_CLAUDE_ROOT")
    if not gpt_root or not claude_root:
        raise RuntimeError("JUDGE_GPT_ROOT and JUDGE_CLAUDE_ROOT must be set.")

    out_csv = OUT / "kappa_summary.csv"
    rows = []
    for combo in COMBINATIONS:
        g = load_verdicts(Path(gpt_root) / combo)
        c = load_verdicts(Path(claude_root) / combo)
        common = sorted(set(g.keys()) & set(c.keys()))
        if not common:
            rows.append({"combination": combo, "n": 0,
                         "gpt_det": 0, "claude_det": 0,
                         "agreement_pct": 0.0, "kappa": 0.0})
            continue
        n = len(common)
        p_a = sum(1 for k in common if g[k])
        p_b = sum(1 for k in common if c[k])
        both = sum(1 for k in common if g[k] and c[k])
        agree_tt = both
        agree_ff = n - p_a - p_b + both
        agreement_pct = 100.0 * (agree_tt + agree_ff) / n
        k = cohens_kappa(p_a, p_b, n, both)
        rows.append({"combination": combo, "n": n,
                     "gpt_det": p_a, "claude_det": p_b,
                     "agreement_pct": agreement_pct, "kappa": k})

    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["combination", "n", "gpt_det", "claude_det",
                                          "agreement_pct", "kappa"])
        w.writeheader()
        for r in rows:
            r["agreement_pct"] = f"{r['agreement_pct']:.2f}"
            r["kappa"] = f"{r['kappa']:.3f}"
            w.writerow(r)

    print(f"[saved] {out_csv}")
    # Print a compact summary
    kappas = [float(r["kappa"]) for r in rows if int(r["n"]) > 0]
    if kappas:
        print(f"kappa range: [{min(kappas):.3f}, {max(kappas):.3f}]")
        print(f"total cells: {sum(int(r['n']) for r in rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
