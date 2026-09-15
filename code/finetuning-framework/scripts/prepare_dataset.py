"""prepare_dataset.py -- build the 4-phase JSONL training corpus.

Drives the dataset_builder pipeline end-to-end:
  1. Walk a skill collection.
  2. Call the teacher model (gpt-4o-mini by default; overridable via --teacher)
     for each skill to produce Phase 1..4 reasoning trajectories.
  3. Validate the JSONL structure (schema-v3 four-section assistant turns).
  4. Split into train.jsonl / val.jsonl / test.jsonl (stratified on is_malicious).

Requires OPENAI_API_KEY at run time (the teacher is called via the OpenAI API).
The default teacher is the inexpensive gpt-4o-mini; pass --teacher gpt-5.4 to
reproduce the paper's production teacher.

Usage:
    python scripts/prepare_dataset.py \\
        --skills-dir experiments/sample \\
        --teacher gpt-4o-mini \\
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
                    help="Root of the skill collection (one SKILL.md per skill dir).")
    ap.add_argument("--teacher", default="gpt-4o-mini",
                    help="Teacher model name (default: gpt-4o-mini; e.g. gpt-5.4 for the "
                         "paper's production teacher).")
    ap.add_argument("--provider", default="openai",
                    help="Teacher provider label (default: openai).")
    ap.add_argument("--iters", default="0,1,2",
                    help="Comma-separated mutation iterations to include for "
                         "mutation-tree skills (default: '0,1,2').")
    ap.add_argument("--output-dir", required=True,
                    help="Output dataset directory (writes train/val/test.jsonl).")
    ap.add_argument("--val-fraction", type=float, default=0.15,
                    help="Fraction of samples used for the validation split.")
    args = ap.parse_args()

    # Local imports so --help works without the heavy deps installed.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from skill_scanner_finetune.dataset_builder import formatter_v3, splitter, validator  # noqa: E402

    skills_dir = Path(args.skills_dir).resolve()
    out_dir = Path(args.output_dir).resolve()
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    iters = [int(x) for x in args.iters.split(",") if x.strip() != ""]

    print(f"[1/3] Building 4-phase trajectories from {skills_dir} "
          f"(teacher={args.teacher}, iters={iters}) ...")
    raw_jsonl = raw_dir / "full.jsonl"
    formatter_v3.build_corpus(skills_dir=skills_dir, teacher_model=args.teacher,
                              iters=iters, output_path=raw_jsonl, provider=args.provider)

    print("[2/3] Validating schema ...")
    errors = validator.validate(raw_jsonl)
    if errors:
        print(f"[error] {len(errors)} entries failed validation; first 3:")
        for e in errors[:3]:
            print(f"  - {e}")
        return 1

    print(f"[3/3] Splitting train/val/test (val_fraction={args.val_fraction}) ...")
    train_ratio = max(0.0, 1.0 - 2 * args.val_fraction)
    stats = splitter.split_dataset(raw_dir=raw_dir, combined_dir=out_dir,
                                   train_ratio=train_ratio, val_ratio=args.val_fraction)
    print(f"[done] {out_dir}/train.jsonl, val.jsonl, test.jsonl written "
          f"(train={stats.get('train')}, val={stats.get('val')}, test={stats.get('test')}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
