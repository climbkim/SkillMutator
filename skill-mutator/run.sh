#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# SkillMutator reproduction demo — mutate a sample skill, scan it, and build
# the mutation-side paper floats from the run:
#
#     Table III  (safety-refusal summary)
#     Table IV   (cross-scanner detection matrix)
#     Table V    (select vs no-select)
#     Figure 4   (Iterative Evasion Refinement per-iteration dynamics)
#
# These are the same floats the CPU-only claims (claim01 / claim02 / claim03 /
# claim09) verify against bundled verdicts; this script regenerates them LIVE
# from the released pipeline so the code path is demonstrably exercised.
#
#   *** REQUIRES an OpenAI API key (OPENAI_API_KEY). ***
# The adversarial oracle (mutation), the LLM scanner, and the judge all call the
# OpenAI API. The default model is the cheapest, gpt-4o-mini; override it below.
# The key is taken from the environment, or auto-loaded from a .env file.
#
# DEMO SCALE: by default this runs ONE sample skill against ONE oracle, so the
# generated floats prove the flow and show the paper's exact format — the
# numbers are sample-scale, NOT the paper's. Reproducing the paper's actual
# numbers needs the full benchmark (17 skills x 13 categories x 3 oracles x 5
# scanners + GPT-5.4 judge); see docs/REPRODUCE.md.
#
# Usage:
#   ./run.sh                         # sample skill, gpt-4o-mini oracle+scanner+judge
#   ./run.sh --model gpt-5.4-mini    # change the oracle / LLM-scanner model
#   ./run.sh --judge-model gpt-5.4   # change the judge model (paper uses gpt-5.4)
#   ./run.sh --skill path/to/skill   # mutate a different skill folder
#   ./run.sh --env-file path/to/.env # load OPENAI_API_KEY from this .env file
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")"

MODEL="gpt-4o-mini"
JUDGE_MODEL="gpt-4o-mini"
SKILL="examples/skills/sample_skill"
ENV_FILE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --model)       MODEL="$2"; shift 2 ;;
    --judge-model) JUDGE_MODEL="$2"; shift 2 ;;
    --skill)       SKILL="$2"; shift 2 ;;
    --env-file)    ENV_FILE="$2"; shift 2 ;;
    -h|--help)     sed -n '2,32p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1 (try --help)"; exit 2 ;;
  esac
done

# Auto-load OPENAI_API_KEY from a .env file if it is not already in the
# environment, so `./run.sh` works as a single command. Search order:
# --env-file, then .env beside run.sh and up to three parent directories.
if [ -z "${OPENAI_API_KEY:-}" ]; then
  for _env in "$ENV_FILE" .env ../.env ../../.env ../../../.env; do
    [ -n "$_env" ] && [ -f "$_env" ] || continue
    _val="$(grep -m1 '^OPENAI_API_KEY=' "$_env" | cut -d= -f2- | tr -d '\r' | sed -e 's/^"//' -e 's/"$//')"
    [ -n "$_val" ] || continue
    export OPENAI_API_KEY="$_val"
    echo "   (loaded OPENAI_API_KEY from $_env)"
    break
  done
fi
: "${OPENAI_API_KEY:?Set OPENAI_API_KEY (env var), or put it in a .env beside run.sh / pass --env-file}"

echo "== SkillMutator demo =="
echo "   oracle/scanner model : $MODEL   (default gpt-4o-mini; override with --model)"
echo "   judge model          : $JUDGE_MODEL (override with --judge-model; paper uses gpt-5.4)"
echo "   skill                : $SKILL"
echo "   NOTE: demo scale (1 skill, 1 oracle). Full paper numbers -> docs/REPRODUCE.md."
echo

# Dependency guard (generation extras).
python3 - <<'PYCHK' || { echo "Missing generation deps. Install: ./install.sh --generate"; exit 1; }
import importlib.util, sys
need = ("openai","langchain_core","langchain_openai","langgraph","tiktoken","dotenv")
sys.exit(1 if [m for m in need if importlib.util.find_spec(m) is None] else 0)
PYCHK

RESULTS="./demo-results"
export SKILLMUTATOR_DATA_ROOT="${SKILLMUTATOR_DATA_ROOT:-$PWD/demo-data}"
export SKILLMUTATOR_ORACLE="$MODEL"   # Table V (select) uses this oracle

echo "== [0/4] Clean prior demo artifacts (fresh run) =="
rm -rf "$RESULTS" "$SKILLMUTATOR_DATA_ROOT" baseline_result analysis/rq1/scripts/outputs analysis/rq2/scripts/outputs analysis/paper_floats/outputs

echo "== [1/4] Mutate the sample skill (oracle=$MODEL, 1 refinement iteration) =="
python scripts/run_mutation.py "$SKILL" \
    --provider openai --model "$MODEL" \
    --mode select --max-iters 1 --use-llm-detect \
    --result-dir "$RESULTS"

echo "== [2/4] Consolidate the run into the canonical data tree ($SKILLMUTATOR_DATA_ROOT) =="
python scripts/consolidate_to_datatree.py \
    --result-root "$RESULTS" --oracle "$MODEL" \
    --data-root "$SKILLMUTATOR_DATA_ROOT" --mode select

echo "== [3/4] Populate per-scanner verdicts into the tree (from the run's scan results) =="
# The mutation step (--use-llm-detect) already scanned + adjudicated each cell and
# wrote comparison_<skill>.csv (ss/snyk/llm detected). Bridge those into the
# <cell>/<scanner>/verdict.json cells (and mark classification) the builders read.
python scripts/populate_verdicts.py \
    --comparison-csv "$RESULTS/comparison_$(basename "$SKILL").csv" \
    --oracle "$MODEL" --mode select \
    --data-root "$SKILLMUTATOR_DATA_ROOT" --scanner-model "$MODEL"

echo "== [4/4] Build the paper floats from the run =="
python analysis/paper_floats/table3_refusal.py      || true
python analysis/paper_floats/table4_cross_scanner.py || true
python analysis/paper_floats/table5_select.py        || true
python analysis/paper_floats/figure4_ier.py          || true

# Keep only the paper-labelled per-float folders; drop raw intermediate outputs.
rm -rf analysis/rq1/scripts/outputs analysis/rq2/scripts/outputs

echo
echo "Demo complete. Generated floats (paper format, demo scale):"
echo "   analysis/paper_floats/outputs/<float>/  — one folder per paper float:"
echo "     table3_refusal/  table4_cross_scanner/  table5_select/  figure4_ier/"
echo "Run with the full benchmark + gpt-5.4 judge to reproduce the paper's numbers (docs/REPRODUCE.md)."
