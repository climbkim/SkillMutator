# LoRA adapter release policy

## Status

The fine-tuned LoRA adapter that produced the paper's headline number (88.16 %
detection on the 76-case GPT-5.4 oracle benchmark) is **released** on the
Hugging Face Hub:

    ADAPTER_REPO = climbkim/skillmutator-scanner-adapters

The repo holds one archive per base model
(`Skillmutator_Scanner-<model>.tar.gz` for Qwen / Llama / Mistral / Gemma).
`scripts/fetch_adapter.py` (driven by `run.sh` stage [C]) downloads the archive
for the selected `ADAPTER_MODEL` (default Qwen2.5-Coder-7B-Instruct), extracts it,
and resolves the PEFT adapter directory. Override with `ADAPTER_REPO` /
`ADAPTER_MODEL`.

## Provenance and licensing (please cite / attribute)

The adapter is a LoRA delta over `Qwen/Qwen2.5-Coder-7B-Instruct` (Apache-2.0),
distilled from a frontier teacher (GPT-5.4) over community-authored skills whose
licenses vary per skill. It is released for research reproduction; when you use
it, cite the paper and note that the training data was teacher-distilled. Use is
subject to the base model's license and the OpenAI usage terms governing the
teacher outputs.

## What you can do instead of downloading

- **Re-create the adapter.** [docs/REPRODUCE.md](REPRODUCE.md) walks through
  every step (roughly eight hours on a single A100 80 GB with the provided
  `configs/qwen_default.yaml`).
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
