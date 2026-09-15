# skill-scanner-finetune

> Four-phase fine-tuning framework for a locally deployable LLM agent-skill scanner.

`skill-scanner-finetune` fine-tunes a base LLM (e.g.
[`Qwen/Qwen2.5-Coder-7B-Instruct`](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct))
into a scanner that flags SKILL.md+code semantic-injection attacks against
LLM agent skills. It runs locally on a single A100-class GPU and avoids
external API calls at inference time.

The benchmark and adversarial mutation side lives in the mutation package of
this repository (`artifact/code/skillmutator/`).

> **Execution requirement — NVIDIA A100 80 GB GPU.** The entire fine-tuning
> pipeline (teacher-driven training-data generation, LoRA fine-tuning, adapter
> merge, and vLLM-served scanning) must run on an NVIDIA A100 80 GB (or
> equivalent) GPU; the reference runs and `~8 h` full-training figure assume an
> A100 80 GB. This framework is **not** part of the CPU-only claim-verification
> path — those checks live separately under `claims/` and need no GPU or API key.

## Features

- **Four-phase analysis schema** — Purpose Grounding → Out-of-Scope Detection
  → Security Principle Reasoning → Attack Category Labeling. Each phase
  produces a structured artifact the next phase consumes.
- **Teacher distillation** — a frontier teacher (e.g. GPT-5.4) generates
  per-skill four-phase traces; the trainer turns those traces into a JSONL
  corpus.
- **Deterministic refinement** — for samples whose teacher Phase 4 missed the
  ground-truth attack category, an evidence-grounded bullet is injected into
  the training data with no extra LLM calls.
- **LoRA fine-tuning** — TRL + PEFT recipe (r=64, α=128, lr=5e-5, 5 epochs,
  bf16). All hyperparameters are overridable via the YAML config.
- **Forced Prefix Pre-filling** — at inference time the scanner injects the
  Phase 4 header as an assistant continuation, forcing small open-source
  models to reliably reach the verdict stage.
- **vLLM serving** — a thin client wraps vLLM's OpenAI-compatible chat API for
  scalable local inference.

## Install

```bash
git clone https://github.com/climbkim/SkillMutator.git
cd SkillMutator/finetuning-framework
pip install -e .[all]                # pulls in the skillmutator package
cp .env.example .env                  # then edit OPENAI_API_KEY, HF_TOKEN, OUTPUT_DIR
```

Requirements: Python 3.10+, an A100 80 GB (or equivalent) for training, and a
HuggingFace token for downloading the base model.

## Quickstart

```bash
# 1. Build the four-phase training set (uses a frontier teacher; non-trivial cost).
python scripts/prepare_dataset.py --skills-dir <your-skills>/

# 2. Pre-flight smoke test (5 steps; verify LoRA wraps and loss is finite).
python scripts/train.py \
       --config src/skill_scanner_finetune/finetune/configs/qwen_default.yaml \
       --max-steps 5

# 3. Full fine-tuning run (~8 h on a single A100 80 GB).
python scripts/train.py \
       --config src/skill_scanner_finetune/finetune/configs/qwen_default.yaml

# 4. Merge the LoRA adapter into a serving checkpoint.
python -m skill_scanner_finetune.finetune.merge_lora \
       --base Qwen/Qwen2.5-Coder-7B-Instruct \
       --adapter ${OUTPUT_DIR}/qwen2.5-coder-7b/final \
       --out     ${OUTPUT_DIR}/qwen2.5-coder-7b-merged

# 5. Serve via vLLM and scan a skill.
vllm serve ${OUTPUT_DIR}/qwen2.5-coder-7b-merged \
       --port 8000 --max-model-len 32768 --dtype bfloat16 &
python scripts/run_scanner.py path/to/skill \
       --backend vllm --base-url http://localhost:8000/v1 \
       --model qwen2.5-coder-7b-merged \
       --prefill "## Phase 4: Category Mapping"
```

## The four-phase schema

| Phase | Display name                  | Purpose                                              | Output kind |
|-------|-------------------------------|------------------------------------------------------|-------------|
| P1    | Purpose Grounding             | Extract the skill's minimal declared purpose         | JSON        |
| P2    | Out-of-Scope Detection        | Enumerate operations exceeding the declared scope    | JSON        |
| P3    | Security Principle Reasoning  | Map evidence to nine security principles (P1–P9)     | Markdown    |
| P4    | Attack Category Labeling      | Label principle violations with 13 attack categories | Markdown    |

Forced Prefix Pre-filling injects the literal Phase 4 section header
(`## Phase 4: Category Mapping`) as an assistant continuation at inference
time. The model is then conditioned on the same context its verdict head was
trained on, while skipping the cumulative latency of regenerating Phases 1–3.
Details in [`docs/PIPELINE.md`](docs/PIPELINE.md).

## Configuration

| Env var            | Purpose                                                  |
|--------------------|----------------------------------------------------------|
| `OPENAI_API_KEY`   | Teacher model + LLM judge during dataset preparation     |
| `HF_TOKEN`         | HuggingFace model downloads                              |
| `OUTPUT_DIR`       | Where checkpoints and merged adapters land               |
| `DATASET_DIR`      | Where the JSONL training corpus is written               |
| `VLLM_BASE_URL`    | vLLM serving endpoint (default `http://localhost:8000/v1`) |
| `WANDB_API_KEY`    | Optional, for training-run tracking                      |

## Project layout

```
skill-scanner-finetune/
├── src/skill_scanner_finetune/
│   ├── analysis_phases/      # P1..P4 phase prompts + driver
│   ├── dataset_builder/      # teacher traces -> four-phase JSONL corpus
│   ├── finetune/             # train.py + configs/qwen_default.yaml + merge helper
│   ├── scanner/              # vLLM wrapper + Forced Prefix Pre-filling
│   └── utils/
├── examples/skills/          # sample skills for the smoke test
├── scripts/                  # prepare_dataset, train, run_scanner
├── docs/                     # USAGE, PIPELINE, ADAPTER_POLICY
└── tests/
```

## LoRA adapter availability

The pre-trained LoRA adapter is **released** on the Hugging Face Hub
(`ADAPTER_REPO = climbkim/skillmutator-scanner-adapters`). `run.sh` stage
[C] downloads it with `scripts/fetch_adapter.py`; you can also re-create it from
scratch via the full pipeline. See [`docs/ADAPTER_POLICY.md`](docs/ADAPTER_POLICY.md)
for provenance, licensing, and attribution.

## License

MIT. See [LICENSE](LICENSE).

## Citation

If you use this codebase, please cite the accompanying paper:

```bibtex
@inproceedings{skillmutator2026,
  title  = {<paper title — to fill in>},
  author = {<authors — anonymized>},
  year   = {2026},
}
```
