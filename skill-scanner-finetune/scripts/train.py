"""train.py -- thin wrapper around the LoRA fine-tuning entry point.

Equivalent to `python -m skill_scanner_finetune.finetune.train`. The wrapper
exists so the documentation can refer to a stable, shorter command.

The output directory, dataset paths, and hyperparameters all come from the
YAML config (see configs/qwen_default.yaml -> training.output_dir). Edit
the config to change them.

Usage:
    # Pre-flight smoke test (5 steps; verify LoRA wraps and the loss is finite)
    python scripts/train.py \\
        --config src/skill_scanner_finetune/finetune/configs/qwen_default.yaml \\
        --max-steps 5

    # Full training run
    python scripts/train.py \\
        --config src/skill_scanner_finetune/finetune/configs/qwen_default.yaml
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

# Forward all CLI args to the trainer module.
TRAINER = Path(__file__).resolve().parent.parent / "src" / "skill_scanner_finetune" / "finetune" / "train.py"

if not TRAINER.is_file():
    sys.exit(f"[error] trainer not found at {TRAINER}")

sys.argv[0] = str(TRAINER)
runpy.run_path(str(TRAINER), run_name="__main__")