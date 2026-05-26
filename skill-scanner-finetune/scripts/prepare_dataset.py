"""prepare_dataset.py -- build the 4-phase JSONL training corpus.

Drives the dataset_builder pipeline end-to-end:
  1. Walk a skill collection.
  2. Call the teacher model (GPT-5.4 by default) for each (skill, attack-cat,
     iter) to produce Phase 1..4 reasoning trajectories.
  3. Apply label refinement (deterministic; injects ground-truth bullets when
     the teacher missed the injected category).
  4. Validate against the v3 schema and split into train.jsonl + val.jsonl.

Usage:
    python scripts/prepare_dataset.py \\
        --skills-dir <your-50-skills>/ \\
        --teacher gpt-5.4 \\
        --iters 0,1,2 \\
        --output-dir ${DATASET_DIR}
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the four-phase training corpus.")
    ap.add_argument("--skills-dir", required=True,
                    help="Root of the community-skill collection (one subdir per skill).")
    ap.add_argument("--teacher", default="gpt-5.4",
                    help="OpenAI model name for the teacher (default: gpt-5.4).")
    ap.add_argument("--iters", default="0,1,2",
                    help="Comma-separated mutation iterations to include (default: '0,1,2', "
                         "matching the paper's production mix).")
    ap.add_argument("--output-dir", required=True,
                    help="Output dataset directory (writes train.jsonl, val.jsonl).")
    ap.add_argument("--val-fraction", type=float, default=0.15,
                    help="Fraction of samples used for the validation split.")
    args = ap.parse_args()

    # Local imports so --help works without the heavy deps installed.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from skill_scanner_finetune.dataset_builder import formatter_v3, splitter, validator  # noqa: E402

    skills_dir = Path(args.skills_dir).resolve()
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    iters = [int(x) for x in args.iters.split(",")]

    print(f"[1/3] Building 4-phase trajectories from {skills_dir} "
          f"(teacher={args.teacher}, iters={iters}) ...")
    full_jsonl = out_dir / "full_dataset.jsonl"
    if hasattr(formatter_v3, "build_corpus"):
        formatter_v3.build_corpus(skills_dir=skills_dir, teacher_model=args.teacher,
                                  iters=iters, output_path=full_jsonl)
    else:
        print("[warn] formatter_v3.build_corpus(...) not implemented; you will need to "
              "wire the per-skill formatter (formatter_v3.format_one(...)) into a loop.",
              file=sys.stderr)
        return 2

    print(f"[2/3] Validating schema ...")
    bad = validator.validate(full_jsonl) if hasattr(validator, "validate") else []
    if bad:
        print(f"[error] {len(bad)} samples failed schema validation; first 3:")
        for b in bad[:3]:
            print(f"  - {b}")
        return 1

    print(f"[3/3] Splitting train/val (val_fraction={args.val_fraction}) ...")
    splitter.split(full_jsonl, out_dir, val_fraction=args.val_fraction)
    print(f"[done] {out_dir}/train.jsonl and {out_dir}/val.jsonl written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())