# LoRA adapter release policy

## Status

The fine-tuned LoRA adapter that produced the paper's headline number (88.16 %
detection on the 76-case GPT-5.4 oracle benchmark) is **not released**.

## Why

Two reasons:

1. **Reproducibility, not redistribution.** This package documents the
   training procedure end-to-end. Anyone with the same training corpus, the
   provided config (`configs/qwen_default.yaml`), and a single A100 80 GB
   can reproduce the adapter from scratch in roughly eight hours. We chose to
   release the procedure rather than the artifact.
2. **Training-data licensing.** The adapter was distilled from outputs of a
   proprietary frontier teacher (GPT-5.4) and trained on 50 community-authored
   skills whose licenses vary per skill. We do not have unambiguous
   permission to redistribute weights derived from those inputs.

## What you can do instead

- **Re-create the adapter.** [docs/REPRODUCE.md](REPRODUCE.md) walks through
  every step.
- **Use a different teacher.** If you cannot or do not want to call GPT-5.4,
  the four-phase schema and training pipeline are agnostic to the specific
  teacher — substitute any model that can produce structured `Phase 1..4`
  outputs.
- **Host your re-trained adapter.** If you publish your own re-training,
  please cite the paper and include a note about the dataset / teacher you
  used; that helps the next person interpret your numbers in context.

## Distribution policy for derivatives

Public derivatives (forks, papers using `skill-scanner-finetune` as a baseline,
etc.) may freely include their own LoRA adapters or merged weights, subject to
the licenses of their respective base models and training data. The procedural
parts of this repository are MIT-licensed.
