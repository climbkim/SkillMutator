#!/usr/bin/env bash
# =============================================================================
# finetuning-framework end-to-end reproduction driver.
#
#   [A] data-gen : distill a training corpus from a skill collection (teacher)
#   [B] train    : LoRA fine-tune the base model (demo: a few steps)
#   [C] adapter  : download the RELEASED adapter from the Hub (used for scanning)
#   [D] scan     : scan a mutated skill with the fine-tuned adapter
#   [E] judge    : adjudicate the scan into a judge_summary.csv
#   [F] tables   : render paper-shaped tables/figures FROM THIS RUN's scan data
#
# Tables/figures are generated from the data produced in THIS run, not from
# hard-coded numbers: run it under the paper's setting (full corpora + released
# adapter) and it reproduces the paper's tables; run it in demo mode (the
# defaults below, a single sample skill) and it produces a small illustrative
# table in the same schema.
#
# >>> EXECUTION REQUIREMENT: NVIDIA A100 80 GB GPU. <<<
# The whole pipeline (teacher data-gen, LoRA training, adapter merge/inference)
# assumes an A100 80 GB. This is NOT the CPU-only claim-verification path — that
# lives under ../../claims/ and needs no GPU or API key.
#
# Env knobs (demo defaults shown):
#   MODE=demo|full            demo (default) scans one sample mutated skill
#   SKILLS_DIR=experiments/sample        corpus for [A] data-gen
#   SCAN_TARGET=experiments/sample/skill_mutated   skill scanned in [D] (demo)
#   SCAN_CATEGORY="Data Exfiltration"    injected category of SCAN_TARGET (demo)
#   TEACHER=gpt-4o-mini       teacher model for [A] (cost-friendly default)
#   ADAPTER_REPO=<hf repo id> released adapter to download in [C] (REQUIRED for D-F)
#   BASE_MODEL=Qwen/Qwen2.5-Coder-7B-Instruct
#   OUTPUT_DIR=./output_demo
#   MAX_STEPS=5               demo training steps for [B]
#   SKIP_TRAIN=0 SKIP_SCAN=0  set to 1 to skip a stage
#
# Requires OPENAI_API_KEY (teacher in [A]; judge in [E]).
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"

# load a .env if present (OPENAI_API_KEY, ADAPTER_REPO, ...) before reading vars
for envf in .env ../.env ../code/.env; do
  if [ -f "$envf" ]; then set -a; . "$envf"; set +a; echo "[run.sh] loaded env: $envf"; break; fi
done

MODE="${MODE:-demo}"
SKILLS_DIR="${SKILLS_DIR:-experiments/sample}"
SCAN_TARGET="${SCAN_TARGET:-experiments/sample/skill_mutated}"
SCAN_CATEGORY="${SCAN_CATEGORY:-Data Exfiltration}"
TEACHER="${TEACHER:-gpt-4o-mini}"
JUDGE_MODEL="${JUDGE_MODEL:-gpt-4o-mini}"
BASE_MODEL="${BASE_MODEL:-Qwen/Qwen2.5-Coder-7B-Instruct}"
ADAPTER_REPO="${ADAPTER_REPO:-climbkim/skillmutator-scanner-adapters}"
ADAPTER_MODEL="${ADAPTER_MODEL:-Qwen2.5-Coder-7B-Instruct}"
OUTPUT_DIR="${OUTPUT_DIR:-./output_demo}"
MAX_STEPS="${MAX_STEPS:-5}"
SKIP_TRAIN="${SKIP_TRAIN:-0}"
SKIP_SCAN="${SKIP_SCAN:-0}"
CONFIG="src/skill_scanner_finetune/finetune/configs/qwen_default.yaml"

PY="${PYTHON:-python}"
# make `python -m skill_scanner_finetune...` importable without pip-installing
export PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p "$OUTPUT_DIR"

echo "=============================================================="
echo " finetuning-framework run.sh  (MODE=$MODE)  [GPU required for C-E]"
echo "=============================================================="

: "${OPENAI_API_KEY:?[run.sh] OPENAI_API_KEY is required (teacher for [A], judge for [E]). Put it in a .env file.}"

# --- [A] training-data generation --------------------------------------------
echo; echo "== [A] data-gen: distill training corpus from $SKILLS_DIR (teacher=$TEACHER) =="
"$PY" scripts/prepare_dataset.py \
    --skills-dir "$SKILLS_DIR" \
    --teacher    "$TEACHER" \
    --output-dir "$OUTPUT_DIR/dataset"

# --- [B] demo training -------------------------------------------------------
if [ "$SKIP_TRAIN" = "1" ]; then
  echo; echo "== [B] train: SKIPPED (SKIP_TRAIN=1) =="
else
  echo; echo "== [B] train: LoRA fine-tune (demo: --max-steps $MAX_STEPS) =="
  echo "   (this demonstrates the training PROCESS; scanning below uses the"
  echo "    released adapter from [C], not this short demo run)"
  "$PY" scripts/train.py --config "$CONFIG" --max-steps "$MAX_STEPS" \
    || echo "[run.sh] training step returned non-zero (check GPU / config); continuing to scan with the released adapter."
fi

if [ "$SKIP_SCAN" = "1" ]; then
  echo; echo "== [D]-[F] scan/judge/tables: SKIPPED (SKIP_SCAN=1) =="
  echo "[run.sh] done (data-gen + train only)."
  exit 0
fi

# --- [C] download + extract the released adapter -----------------------------
echo; echo "== [C] adapter: download+extract released LoRA adapter ($ADAPTER_MODEL) =="
ADAPTER_DIR="$("$PY" scripts/fetch_adapter.py --repo "$ADAPTER_REPO" --model "$ADAPTER_MODEL" --out "$OUTPUT_DIR/adapter" | tail -1)"
echo "[run.sh] adapter dir: $ADAPTER_DIR"

# --- [D] scan a positive (mutated) and a negative (benign) sample skill ------
SCAN_BENIGN="${SCAN_BENIGN:-experiments/sample/skill}"
mkdir -p "$OUTPUT_DIR/scan"
echo; echo "== [D] scan (positive): $SCAN_TARGET with fine-tuned adapter =="
"$PY" -m skill_scanner_finetune.finetune.infer \
    --base "$BASE_MODEL" --lora "$ADAPTER_DIR" \
    --skill "$SCAN_TARGET" | tee "$OUTPUT_DIR/scan/scan_pos.md"
echo; echo "== [D] scan (negative/unmodified): $SCAN_BENIGN =="
"$PY" -m skill_scanner_finetune.finetune.infer \
    --base "$BASE_MODEL" --lora "$ADAPTER_DIR" \
    --skill "$SCAN_BENIGN" | tee "$OUTPUT_DIR/scan/scan_neg.md"

# --- [E] judge both scans into positive / negative judge_summary CSVs ---------
echo; echo "== [E] judge: adjudicate scans -> judge_summary.csv / judge_neg.csv =="
"$PY" analysis/judge_scan_to_csv.py \
    --scan-file     "$OUTPUT_DIR/scan/scan_pos.md" \
    --skill         "$(basename "$SCAN_TARGET")" \
    --category      "$SCAN_CATEGORY" \
    --injected-file "$SCAN_TARGET/SKILL.md" \
    --judge-model   "$JUDGE_MODEL" \
    --out-csv       "$OUTPUT_DIR/scan/judge_summary.csv"
"$PY" analysis/judge_scan_to_csv.py \
    --scan-file     "$OUTPUT_DIR/scan/scan_neg.md" \
    --skill         "$(basename "$SCAN_BENIGN")" \
    --category      "NONE" \
    --injected-file "$SCAN_BENIGN/SKILL.md" \
    --judge-model   "$JUDGE_MODEL" \
    --out-csv       "$OUTPUT_DIR/scan/judge_neg.csv"

# --- [F] render every fine-tuning-side float as a claims-mirroring CSV --------
echo; echo "== [F] tables: build paper-structured CSVs from this run's data =="
"$PY" analysis/build_claim_tables.py \
    --judge-csv "$OUTPUT_DIR/scan/judge_summary.csv" \
    --neg-csv   "$OUTPUT_DIR/scan/judge_neg.csv" \
    --out-dir   "$OUTPUT_DIR/claim_tables" \
    --label     "$MODE (this run)"

echo; echo "== [F] check: verify generated CSVs match the paper structure =="
"$PY" analysis/check_claim_tables.py --tables-dir "$OUTPUT_DIR/claim_tables"

echo; echo "=============================================================="
echo " done. paper-structured CSVs (claims-mirroring) -> $OUTPUT_DIR/claim_tables"
echo " one subdir per float (claim04/05/06/07/08/11/12), each a CSV in the"
echo " paper's row/column structure; measured cells filled from this run,"
echo " multi-run cells left as skeleton (status=full-mode)."
echo "=============================================================="
echo
echo "To reproduce the paper's numbers instead of the demo: set MODE=full,"
echo "point SKILLS_DIR at the full training corpus and SCAN_TARGET at the"
echo "n=76 GPT-5.4-oracle mutation tree (batch scan via"
echo "finetune/eval_infer_vllm.py), then build the multi-model/variant floats"
echo "with analysis/rq3/scripts/build_tab_finetune.py (Figure 5) and"
echo "analysis/rq4/scripts/build_tab_phase_ablation.py (Table VI)."
