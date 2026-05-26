#!/usr/bin/env bash
# reproduce_all.sh — produce every paper artifact in evaluate/outputs/.
#
# Prereqs (set before invoking):
#   export SKILLMUTATOR_DATA_ROOT=/path/to/Skillmutator-data
#   export FINETUNE_SCAN_ROOT=/path/to/finetune-scan-outputs
#   export FINETUNE_BASELINE_ROOT=/path/to/finetune-baseline
#   export JUDGE_GPT_ROOT=/path/to/judge-gpt5.4-verdicts        # (optional, for kappa)
#   export JUDGE_CLAUDE_ROOT=/path/to/judge-claude-verdicts     # (optional, for kappa)
#
# Each script writes its outputs to evaluate/outputs/ and prints a one-line
# `[saved]` summary on success. Failures abort the chain.

set -euo pipefail

EVAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$EVAL_DIR"

run() {
    echo ""
    echo "==> $1"
    python "$1"
}

echo "=== Tables ==="
run scripts/tables/table3_cross_matrix.py
run scripts/tables/table4_refusal_summary.py
run scripts/tables/table5_select_vs_noselect.py
run scripts/tables/table6_prefill_delta.py
run scripts/tables/table7_phase_ablation.py
run scripts/tables/appendix_b1_baseline.py
run scripts/tables/appendix_b2_cell_matrix.py

echo ""
echo "=== Figures ==="
# IER dynamics needs the per-iter compute step first to (re)generate the CSV.
run scripts/figures/figure_ier_dynamics_compute.py
run scripts/figures/figure_ier_dynamics.py
run scripts/figures/figure_fp_per_cat.py

echo ""
echo "=== Stats ==="
if [[ -n "${JUDGE_GPT_ROOT:-}" && -n "${JUDGE_CLAUDE_ROOT:-}" ]]; then
    run scripts/stats/compute_kappa.py
else
    echo "  (skipping kappa: set JUDGE_GPT_ROOT and JUDGE_CLAUDE_ROOT to compute)"
fi
run scripts/stats/compute_paper_cited_values.py

echo ""
echo "All artifacts in $EVAL_DIR/outputs/"
