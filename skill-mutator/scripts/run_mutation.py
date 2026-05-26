"""run_mutation.py -- single-skill mutation runner.

Convenience wrapper around the SkillMutator pipeline for the common case of
mutating one skill end-to-end. For batch sweeps across many skills, see
`run_all_skills.py`.

Usage:
    python scripts/run_mutation.py path/to/skill \\
        --provider openai --model gpt-5.4-mini \\
        --mode select --max-iters 5 \\
        --result-dir ./results/my-eval

The skill folder must contain a `SKILL.md`. Outputs land at
    {result-dir}/{skill_name}/{timestamp}/generate_skill/{attack_category}/iter_K/

with one mutated `SKILL.md` and a `meta.json` per iteration per attack category.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("skill_path", help="Path to a skill folder (containing SKILL.md).")
    ap.add_argument("--provider", default="openai",
                    choices=["openai", "claude-code", "claude", "anthropic",
                             "google", "huggingface"])
    ap.add_argument("--model", default="gpt-5.4-mini",
                    help="Oracle LLM that produces the adversarial mutation.")
    ap.add_argument("--mode", choices=["select", "no-select"], default="select",
                    help="`select` lets the oracle pick the best attack category; "
                         "`no-select` mutates all categories.")
    ap.add_argument("--max-iters", type=int, default=5,
                    help="Number of evasion-refinement iterations (paper default: 5).")
    ap.add_argument("--result-dir", default="./results",
                    help="Output root directory.")
    ap.add_argument("--use-llm-detect", action="store_true",
                    help="Use the LLM scanner during the refinement loop.")
    args = ap.parse_args()

    skill_path = Path(args.skill_path).resolve()
    if not (skill_path / "SKILL.md").is_file():
        print(f"[error] {skill_path}/SKILL.md not found", file=sys.stderr)
        sys.exit(1)

    # Delegate to skill_mutator.main, which is the canonical entry point.
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    cmd = [
        sys.executable, "-m", "skill_mutator.main",
        str(skill_path),
        "--provider", args.provider,
        "--model", args.model,
        "--iterations", str(args.max_iters),
        "--result-dir", args.result_dir,
    ]
    if args.mode == "no-select":
        cmd.append("--no-select")
    if args.use_llm_detect:
        cmd.append("--use-llm-detect")

    print("[run]", " ".join(cmd))
    sys.exit(subprocess.call(cmd, env=env))


if __name__ == "__main__":
    main()
