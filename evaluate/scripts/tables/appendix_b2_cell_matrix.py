"""Paper Appendix B.2 (`tab:cell_metrics`) — cell-level confusion matrix for
the fine-tuned Qwen scanner.

  - Negative population: 17 × 13 = 221 (unmodified skill × canonical category)
  - Positive population: 76 (mutated skill × injected category) from the GPT-5.4
    oracle evaluation set
  - A cell is "fired" if the corresponding Phase 4 section contains a bullet
    that is not `(none)`.

Inputs (all under $FINETUNE_BASELINE_ROOT):
  - cells_unmodified.csv  (columns: skill, category, fired_bool)
  - cells_mutated.csv     (columns: skill, category, fired_bool, target_bool)

Outputs:
  outputs/appendix_b2_cell_matrix.{csv,tex}
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


def load_csv(p: Path) -> list[dict]:
    if not p.is_file():
        raise RuntimeError(f"missing input: {p}")
    with p.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> int:
    root = os.environ.get("FINETUNE_BASELINE_ROOT")
    if not root:
        raise RuntimeError("FINETUNE_BASELINE_ROOT not set.")
    root_p = Path(root)
    unmod = load_csv(root_p / "cells_unmodified.csv")
    mut   = load_csv(root_p / "cells_mutated.csv")

    # Mutated positive set: detected = fired AND target_category == injected_category.
    # In our schema each row already corresponds to the (skill, injected_category)
    # pair, so target_bool == fired_bool of that target row.
    tp = sum(1 for r in mut if r.get("fired_bool", "").strip().lower() == "true")
    fn = len(mut) - tp

    # Unmodified negatives: each row fired == FP.
    fp = sum(1 for r in unmod if r.get("fired_bool", "").strip().lower() == "true")
    tn = len(unmod) - fp

    metrics = {
        "TP": tp, "FN": fn, "FP": fp, "TN": tn,
        "Recall (TPR)":      tp / (tp + fn) * 100 if (tp + fn) else 0.0,
        "Precision":         tp / (tp + fp) * 100 if (tp + fp) else 0.0,
        "F1":                2 * tp / (2 * tp + fp + fn) * 100 if (2 * tp + fp + fn) else 0.0,
        "Specificity":       tn / (tn + fp) * 100 if (tn + fp) else 0.0,
        "Balanced Accuracy": (tp / (tp + fn) + tn / (tn + fp)) * 50 if (tp + fn) and (tn + fp) else 0.0,
    }

    csv_path = OUT / "appendix_b2_cell_matrix.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["quantity", "value"])
        for k in ("TP", "FN", "FP", "TN"):
            w.writerow([k, metrics[k]])
        for k in ("Recall (TPR)", "Precision", "F1", "Specificity", "Balanced Accuracy"):
            w.writerow([k, f"{metrics[k]:.2f}"])

    L = []
    L.append(r"\begin{table}[t]")
    L.append(r"\centering")
    L.append(rf"\caption{{Cell-level confusion matrix for the fine-tuned Qwen scanner (prefill, GPT-5.4 oracle, $n_{{\text{{mut}}}}{{=}}{len(mut)}$, $n_{{\text{{unmod}}}}{{=}}{len(unmod)}$). FP cells are extracted directly from the Phase~4 grid of the unmodified-skill scans.}}")
    L.append(r"\label{tab:cell_metrics}")
    L.append(r"\footnotesize")
    L.append(r"\setlength{\tabcolsep}{6pt}")
    L.append(r"\begin{tabular}{lr}")
    L.append(r"\toprule")
    L.append(r"\textbf{Quantity} & \textbf{Value} \\")
    L.append(r"\midrule")
    for k in ("TP", "FN", "FP", "TN"):
        L.append(rf"{k} & {metrics[k]} \\")
    L.append(r"\midrule")
    for k in ("Recall (TPR)", "Precision", "F1", "Specificity", "Balanced Accuracy"):
        L.append(rf"{k} & {metrics[k]:.2f}\% \\")
    L.append(r"\bottomrule")
    L.append(r"\end{tabular}")
    L.append(r"\end{table}")
    (OUT / "appendix_b2_cell_matrix.tex").write_text("\n".join(L), encoding="utf-8")

    print(f"[saved] {csv_path}")
    print(f"[saved] {OUT / 'appendix_b2_cell_matrix.tex'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
