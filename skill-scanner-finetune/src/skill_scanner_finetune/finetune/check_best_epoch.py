"""Print the epoch number of the best checkpoint after training.

Usage:
    OUTPUT_DIR=/path/to/run python check_best_epoch.py
    # or pass it as a CLI arg:
    python check_best_epoch.py /path/to/run
"""
import json
import os
import sys
from pathlib import Path

OUTPUT_DIR = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("OUTPUT_DIR", "./output")

state_path = Path(OUTPUT_DIR) / "final" / "trainer_state.json"
if not state_path.exists():
    # Fall back to the most recent checkpoint if `final/` is missing.
    checkpoints = sorted(Path(OUTPUT_DIR).glob("checkpoint-*/trainer_state.json"))
    if checkpoints:
        state_path = checkpoints[-1]
    else:
        print(f"[ERROR] trainer_state.json not found in {OUTPUT_DIR}")
        sys.exit(1)

state = json.loads(state_path.read_text())
best_ckpt = state.get("best_model_checkpoint", "unknown")
best_metric = state.get("best_metric", "unknown")

# Compute epoch as step / steps_per_epoch.
step = int(best_ckpt.split("-")[-1]) if best_ckpt != "unknown" else 0
# Estimate steps_per_epoch from log_history.
log = state.get("log_history", [])
eval_steps = [e["step"] for e in log if "eval_loss" in e]
if len(eval_steps) >= 2:
    steps_per_epoch = eval_steps[1] - eval_steps[0]
else:
    steps_per_epoch = eval_steps[0] if eval_steps else step

epoch = step // steps_per_epoch if steps_per_epoch > 0 else "?"

print(f"Best checkpoint : {best_ckpt}")
print(f"Best eval_loss  : {best_metric}")
print(f"Best epoch      : {epoch}")
print(f"Steps per epoch : {steps_per_epoch}")

# Print eval_loss for every epoch
print("\nAll epoch eval_loss:")
for e in log:
    if "eval_loss" in e:
        ep = e.get("epoch", "?")
        print(f"  epoch {ep}: eval_loss={e['eval_loss']:.4f}")
