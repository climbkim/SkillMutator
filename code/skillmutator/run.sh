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
#   ./run.sh --skill path/to/skill   # mutate a different single skill folder
#   ./run.sh --env-file path/to/.env # load OPENAI_API_KEY from this .env file
#   ./run.sh --crawl 10              # (EXPERIMENTAL) crawl N community skills into
#                                    #   --skills-dir first, then mutate the whole
#                                    #   pool instead of the single sample
#   ./run.sh --crawl 10 --registry clawhub --skills-dir ./skills
#
# NOTE on --crawl: it drives scripts/crawl_skills.py. Bundled registries:
#   --registry anthropic : clone github.com/anthropics/skills, copy the 17 paper
#                          evaluation skills (the mutation-benchmark set).
#   --registry clawhub   : read a ClawHub manifest CSV (artifact/data/clawhub/
#                          clawhub_skills.csv, or $SKILLMUTATOR_CLAWHUB_CSV) and
#                          fetch each skill's SKILL.md from the ClawHub API.
# No skill bodies are redistributed; the backends re-fetch from public sources.
# If no skills are obtained, the demo falls back to the bundled sample skill.
# See docs/SKILLS_SETUP.md.
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")"

MODEL="gpt-4o-mini"
JUDGE_MODEL="gpt-4o-mini"
SKILL="examples/skills/sample_skill"
ENV_FILE=""
CRAWL_N=0
REGISTRY="clawhub"
SKILLS_DIR="./skills"
MAX_ITERS="${MAX_ITERS:-1}"     # Iterative Evasion Refinement iterations (iter_0..N)
MUT_MODE="select"               # select (stealth-aware) | no-select (all 13 categories)
while [ $# -gt 0 ]; do
  case "$1" in
    --model)       MODEL="$2"; shift 2 ;;
    --judge-model) JUDGE_MODEL="$2"; shift 2 ;;
    --skill)       SKILL="$2"; shift 2 ;;
    --env-file)    ENV_FILE="$2"; shift 2 ;;
    --crawl)       CRAWL_N="$2"; shift 2 ;;
    --registry)    REGISTRY="$2"; shift 2 ;;
    --skills-dir)  SKILLS_DIR="$2"; shift 2 ;;
    --iters)       MAX_ITERS="$2"; shift 2 ;;
    --mode)        MUT_MODE="$2"; shift 2 ;;
    -h|--help)     sed -n '2,44p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1 (try --help)"; exit 2 ;;
  esac
done

# Auto-load scanner credentials from a .env file so `./run.sh` works as a
# single command. Search order: --env-file, then .env beside run.sh and up to
# three parent directories; the first file found is used.
#   OPENAI_API_KEY : REQUIRED (adversarial oracle + LLM scanner + judge).
#   SNYK_TOKEN     : OPTIONAL — enables the Snyk Agent scanner. Without it the
#                    Snyk column is left unavailable and the demo still shows
#                    the LLM scanner vs. skill-security (the paper's key story).
#   LLM_PROVIDER / LLM_MODEL : OPTIONAL LLM-scanner defaults.
_load_env_var() {  # $1 = var name; only sets it if not already in the environment
  eval "[ -n \"\${$1:-}\" ]" && return 0
  for _env in "$ENV_FILE" .env ../.env ../../.env ../../../.env; do
    [ -n "$_env" ] && [ -f "$_env" ] || continue
    _val="$(grep -m1 "^$1=" "$_env" 2>/dev/null | cut -d= -f2- | tr -d '\r' | sed -e 's/^"//' -e 's/"$//' || true)"
    [ -n "$_val" ] || continue
    export "$1=$_val"
    echo "   (loaded $1 from $_env)"
    return 0
  done
  return 1
}
_load_env_var OPENAI_API_KEY || true
_load_env_var SNYK_TOKEN    || echo "   (no SNYK_TOKEN found -> Snyk scanner will be skipped/unavailable)"
_load_env_var LLM_PROVIDER  || true
_load_env_var LLM_MODEL     || true
: "${OPENAI_API_KEY:?Set OPENAI_API_KEY (env var), or put it in a .env beside run.sh / pass --env-file}"

# Dependency guard (generation extras).
python3 - <<'PYCHK' || { echo "Missing generation deps. Install: ./install.sh --generate"; exit 1; }
import importlib.util, sys
need = ("openai","langchain_core","langchain_openai","langgraph","tiktoken","dotenv")
sys.exit(1 if [m for m in need if importlib.util.find_spec(m) is None] else 0)
PYCHK

# --- Skill selection ------------------------------------------------------
# Build the list of skills to mutate. Default: the single bundled sample.
# With --crawl N, first populate $SKILLS_DIR via scripts/crawl_skills.py, then
# mutate every skill found there.
SKILLS=()
if [ "$CRAWL_N" -gt 0 ]; then
  echo "== [crawl] fetch $CRAWL_N skills via crawl_skills.py (registry=$REGISTRY -> $SKILLS_DIR) =="
  mkdir -p "$SKILLS_DIR"
  if ! python scripts/crawl_skills.py --registry "$REGISTRY" \
         --target-count "$CRAWL_N" --output-dir "$SKILLS_DIR"; then
    echo "   crawl_skills.py did not produce skills for registry '$REGISTRY'."
    echo "   Check network access (anthropic: git clone; clawhub: ClawHub API +"
    echo "   a manifest CSV via \$SKILLMUTATOR_CLAWHUB_CSV), or drop skills into"
    echo "   $SKILLS_DIR manually (see docs/SKILLS_SETUP.md)."
  fi
  for _d in "$SKILLS_DIR"/*/; do
    [ -f "${_d}SKILL.md" ] && SKILLS+=("${_d%/}")
  done
  if [ "${#SKILLS[@]}" -eq 0 ]; then
    echo "   no crawled skills found -> falling back to the bundled sample skill."
  fi
fi
# No --crawl, but --skills-dir already holds a pool of skills (each a subdir with
# a SKILL.md): mutate all of them. Lets you point the pipeline at your own skills.
if [ "${#SKILLS[@]}" -eq 0 ] && [ -d "$SKILLS_DIR" ]; then
  for _d in "$SKILLS_DIR"/*/; do
    [ -f "${_d}SKILL.md" ] && SKILLS+=("${_d%/}")
  done
  [ "${#SKILLS[@]}" -gt 0 ] && \
    echo "== [pool] mutating ${#SKILLS[@]} skill(s) already in $SKILLS_DIR (no --crawl) =="
fi
[ "${#SKILLS[@]}" -eq 0 ] && SKILLS=("$SKILL")

echo "== SkillMutator demo =="
echo "   oracle/scanner model : $MODEL   (default gpt-4o-mini; override with --model)"
echo "   judge model          : $JUDGE_MODEL (override with --judge-model; paper uses gpt-5.4)"
echo "   skills (${#SKILLS[@]})            : ${SKILLS[*]}"
echo "   NOTE: demo scale (${#SKILLS[@]} skill(s), 1 oracle). Full paper numbers -> docs/REPRODUCE.md."
echo

RESULTS="./demo-results"
export SKILLMUTATOR_DATA_ROOT="${SKILLMUTATOR_DATA_ROOT:-$PWD/demo-data}"
export SKILLMUTATOR_ORACLE="$MODEL"   # Table V (select) uses this oracle

echo "== [0/4] Clean prior demo artifacts (fresh run) =="
rm -rf "$RESULTS" "$SKILLMUTATOR_DATA_ROOT" baseline_result analysis/rq1/scripts/outputs analysis/rq2/scripts/outputs analysis/paper_floats/outputs

echo "== [1/4] Mutate the skill(s) (oracle=$MODEL, 1 refinement iteration) =="
for _skill in "${SKILLS[@]}"; do
  echo "   -> mutating: $_skill"
  python scripts/run_mutation.py "$_skill" \
      --provider openai --model "$MODEL" \
      --mode "$MUT_MODE" --max-iters "$MAX_ITERS" --use-llm-detect \
      --result-dir "$RESULTS"
done

echo "== [2/4] Consolidate the run into the canonical data tree ($SKILLMUTATOR_DATA_ROOT) =="
python scripts/consolidate_to_datatree.py \
    --result-root "$RESULTS" --oracle "$MODEL" \
    --data-root "$SKILLMUTATOR_DATA_ROOT" --mode "$MUT_MODE"

echo "== [3/4] Populate per-scanner verdicts into the tree (from the run's scan results) =="
# The mutation step (--use-llm-detect) already scanned + adjudicated each cell and
# wrote comparison_<skill>.csv (ss/snyk/llm detected). Bridge those into the
# <cell>/<scanner>/verdict.json cells (and mark classification) the builders read.
for _skill in "${SKILLS[@]}"; do
  _csv="$RESULTS/comparison_$(basename "$_skill").csv"
  [ -f "$_csv" ] || { echo "   (no comparison CSV for $(basename "$_skill"), skipping)"; continue; }
  python scripts/populate_verdicts.py \
      --comparison-csv "$_csv" \
      --oracle "$MODEL" --mode "$MUT_MODE" \
      --data-root "$SKILLMUTATOR_DATA_ROOT" --scanner-model "$MODEL"
done

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
