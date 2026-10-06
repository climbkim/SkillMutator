#!/usr/bin/env bash
# =============================================================================
# setup_gpu_server.sh — provision a fresh GPU server for skill-scanner-finetune
#
# Target: a rented single-GPU Linux box (e.g. vast.ai 1xA100 80GB), root user,
# /workspace workdir, no preinstalled ML stack.
#
# What it does, in order:
#   1. Probe the environment (Python, GPU, disk, /dev/shm).
#   2. Create / reuse a venv at $VENV.
#   3. Kill any stale vLLM process left by a previous tenant.
#   4. Install dependencies in a *deliberate order* (torch first), verifying
#      each one — a single combined pip line silently skips packages on failure.
#   5. Patch the `pyairports` stub so vLLM's outlines dependency imports.
#   6. Verify every critical import actually works.
#   7. Print a summary and the exact next commands.
#
# Idempotent: safe to re-run. Re-running only repairs what is missing.
#
# Usage:
#   chmod +x scripts/setup_gpu_server.sh
#   REPO_DIR=/workspace/skill-scanner-finetune ./scripts/setup_gpu_server.sh
#
# Override via env vars:
#   WORKDIR   (default /workspace)
#   VENV      (default $WORKDIR/venv)
#   REPO_DIR  (default: directory two levels above this script)
#   TORCH_INDEX_URL (default https://download.pytorch.org/whl/cu121)
# =============================================================================
set -euo pipefail

# ----------------------------------------------------------------------------
# 0. Configuration
# ----------------------------------------------------------------------------
WORKDIR="${WORKDIR:-/workspace}"
VENV="${VENV:-$WORKDIR/venv}"
_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${REPO_DIR:-$(cd "$_SCRIPT_DIR/.." && pwd)}"
TORCH_INDEX_URL="${TORCH_INDEX_URL:-https://download.pytorch.org/whl/cu121}"

PY="$VENV/bin/python"
PIP="$VENV/bin/pip"

say()  { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }
ok()   { printf '   \033[1;32mOK\033[0m   %s\n' "$*"; }
warn() { printf '   \033[1;33mWARN\033[0m %s\n' "$*"; }
die()  { printf '\n\033[1;31mFATAL: %s\033[0m\n' "$*" >&2; exit 1; }

# ----------------------------------------------------------------------------
# 1. Environment probe
# ----------------------------------------------------------------------------
say "1. Environment probe"
echo "   workdir : $WORKDIR"
echo "   venv    : $VENV"
echo "   repo    : $REPO_DIR"
[ -d "$REPO_DIR/src/skill_scanner_finetune" ] \
    || die "REPO_DIR does not look like skill-scanner-finetune ($REPO_DIR). Set REPO_DIR=..."

if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader \
        | sed 's/^/   GPU: /'
else
    warn "nvidia-smi not found — is this actually a GPU box?"
fi
echo "   disk    : $(df -h "$WORKDIR" | awk 'NR==2{print $4" free on "$6}')"
SHM_FREE="$(df -BG /dev/shm 2>/dev/null | awk 'NR==2{gsub("G","",$4); print $4}')"
echo "   /dev/shm: ${SHM_FREE:-0}G free"
if [ "${SHM_FREE:-0}" -lt 30 ]; then
    warn "/dev/shm < 30G — keep model weights on $WORKDIR/models, not /dev/shm."
fi

SYS_PY="$(command -v python3 || true)"
[ -n "$SYS_PY" ] || die "python3 not found on PATH."
echo "   python3 : $SYS_PY ($("$SYS_PY" --version 2>&1))"

# ----------------------------------------------------------------------------
# 2. venv
# ----------------------------------------------------------------------------
say "2. Virtual environment"
if [ ! -x "$PY" ]; then
    "$SYS_PY" -m venv "$VENV" || die "venv creation failed."
    ok "created venv at $VENV"
else
    ok "venv already present"
fi
"$PIP" install --quiet --upgrade pip setuptools wheel
PYVER="$("$PY" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
ok "venv python $PYVER"

# ----------------------------------------------------------------------------
# 3. Kill stale vLLM from a previous tenant (recurring on shared images)
# ----------------------------------------------------------------------------
say "3. Clear stale GPU processes"
if pgrep -f "vllm" >/dev/null 2>&1; then
    warn "stale vllm process found — killing it"
    pkill -9 -f "vllm" || true
    fuser -k /dev/nvidia* 2>/dev/null || true
    sleep 3
    ok "stale vllm killed"
else
    ok "no stale vllm process"
fi

# ----------------------------------------------------------------------------
# 4. Install dependencies — IN ORDER, verifying each step
#    (a single combined pip line silently skips packages when one fails)
# ----------------------------------------------------------------------------
verify_pkg() {  # verify_pkg <import-name> <pip-name>
    if "$PY" -c "import $1" >/dev/null 2>&1; then
        ok "$2 ($("$PIP" show "$2" 2>/dev/null | awk '/^Version:/{print $2}'))"
    else
        die "$2 failed to import after install — rerun this script."
    fi
}

say "4a. PyTorch (must be installed before everything else)"
if ! "$PY" -c "import torch" >/dev/null 2>&1; then
    "$PIP" install --quiet torch --index-url "$TORCH_INDEX_URL" \
        || "$PIP" install --quiet torch
fi
verify_pkg torch torch
"$PY" -c "import torch; assert torch.cuda.is_available(), 'CUDA not visible to torch'" \
    && ok "torch sees CUDA" || warn "torch.cuda.is_available() is False — check the driver/CUDA image"

say "4b. Training stack (transformers, trl, peft, ...)"
"$PIP" install --quiet \
    "transformers>=4.46.0" \
    "trl>=0.12.0" \
    "peft>=0.13.0" \
    "accelerate>=0.34.0" \
    "bitsandbytes>=0.43.0" \
    "datasets>=2.20.0" \
    "deepspeed>=0.15.0"
for p in transformers:transformers trl:trl peft:peft accelerate:accelerate \
         bitsandbytes:bitsandbytes datasets:datasets deepspeed:deepspeed; do
    verify_pkg "${p%%:*}" "${p##*:}"
done

say "4c. Inference stack (vLLM)"
"$PIP" install --quiet "vllm>=0.6.0"
verify_pkg vllm vllm

say "4d. Support libraries"
"$PIP" install --quiet \
    "openai>=1.0.0" \
    "tiktoken>=0.5.0" \
    "python-dotenv>=1.0.0" \
    "pyyaml>=6.0" \
    "tqdm>=4.65.0" \
    "wandb>=0.17.0"
for p in openai:openai tiktoken:tiktoken dotenv:python-dotenv yaml:pyyaml \
         tqdm:tqdm wandb:wandb; do
    verify_pkg "${p%%:*}" "${p##*:}"
done

say "4e. Install this repo (editable, pulls in skill-mutator as a sister dep)"
# `pip install -e .` resolves skill-mutator from PyPI if published, otherwise
# install the mutation package first with: pip install -e ../skill-mutator
if "$PIP" install --quiet -e "$REPO_DIR" 2>/dev/null; then
    ok "skill-scanner-finetune installed (editable)"
else
    warn "editable install hit a dependency it could not resolve."
    warn "If the skillmutator package is not on PyPI, place it next to this framework and run:"
    warn "    $PIP install -e <path-to-skill-mutator>"
    warn "then re-run: $PIP install -e $REPO_DIR"
fi

# ----------------------------------------------------------------------------
# 5. pyairports stub
#    `pip install pyairports` ships only a sample package; vLLM -> outlines ->
#    `from pyairports.airports import ...` then 500s on every request.
#    We write a minimal real module into the venv site-packages.
# ----------------------------------------------------------------------------
say "5. pyairports stub (vLLM/outlines dependency)"
SITE="$("$PY" -c 'import site; print(site.getsitepackages()[0])')"
PA_DIR="$SITE/pyairports"
if "$PY" -c "from pyairports.airports import Airports" >/dev/null 2>&1; then
    ok "pyairports already importable"
else
    mkdir -p "$PA_DIR"
    : > "$PA_DIR/__init__.py"
    cat > "$PA_DIR/airports.py" <<'PYAIRPORTS'
"""Minimal pyairports stand-in.

The public `pyairports` PyPI package ships only a sample module, so vLLM's
`outlines` dependency fails to import it. This stub provides just enough
surface for those imports to succeed.
"""


class Airport:
    def __init__(self, iata="", icao="", name="", city="",
                 country="", lat=0.0, lng=0.0):
        self.iata = iata
        self.icao = icao
        self.name = name
        self.city = city
        self.country = country
        self.lat = lat
        self.lng = lng


class Airports:
    def __init__(self):
        self.airport_list = []


AIRPORT_LIST = []
PYAIRPORTS
    "$PY" -c "from pyairports.airports import Airports" >/dev/null 2>&1 \
        && ok "pyairports stub written to $PA_DIR" \
        || die "pyairports stub still not importable."
fi

# ----------------------------------------------------------------------------
# 6. Final import verification
# ----------------------------------------------------------------------------
say "6. Verify critical imports"
"$PY" - <<'PYCHECK'
import importlib, sys
mods = ["torch", "transformers", "trl", "peft", "accelerate", "datasets",
        "vllm", "openai", "tiktoken", "yaml", "dotenv"]
bad = []
for m in mods:
    try:
        importlib.import_module(m)
    except Exception as e:
        bad.append(f"{m}: {type(e).__name__} {e}")
if bad:
    print("   IMPORT FAILURES:")
    for b in bad:
        print("    -", b)
    sys.exit(1)
import torch
print(f"   torch {torch.__version__}, CUDA available: {torch.cuda.is_available()}")
print("   all critical imports OK")
PYCHECK
ok "import verification passed"

# ----------------------------------------------------------------------------
# 7. Summary + next steps
# ----------------------------------------------------------------------------
say "Setup complete"
cat <<EOF
  venv     : $VENV   (activate: source $VENV/bin/activate)
  repo     : $REPO_DIR
  python   : $PYVER

  Next steps:
    1) cp $REPO_DIR/.env.example $REPO_DIR/.env   # fill OPENAI_API_KEY, HF_TOKEN
    2) export OUTPUT_DIR=$WORKDIR/output DATASET_DIR=$WORKDIR/dataset
    3) Download the base model:
         hf download Qwen/Qwen2.5-Coder-7B-Instruct --local-dir $WORKDIR/models/qwen2.5-coder-7b
    4) SMOKE TEST before the full run (do NOT skip — see docs/REPRODUCE.md):
         $PY $REPO_DIR/scripts/train.py \\
             --config $REPO_DIR/src/skill_scanner_finetune/finetune/configs/qwen_default.yaml \\
             --max-steps 5
       Confirm: "trainable: X / Y (Z%)" printed, 5 step losses are finite & decreasing.
    5) Full training:
         $PY $REPO_DIR/scripts/train.py \\
             --config $REPO_DIR/src/skill_scanner_finetune/finetune/configs/qwen_default.yaml

  Reminders (recurring pitfalls):
    - Do not trust any orchestrator "ALL DONE" line — confirm judge_summary.csv
      exists AND has > 1 line.
    - Gemma-2 needs --max-model-len 8192 (not 32768) and a system-role patch.
    - Stop/Destroy the instance from the provider dashboard when finished —
      it is NOT auto-stopped and keeps billing.
EOF
