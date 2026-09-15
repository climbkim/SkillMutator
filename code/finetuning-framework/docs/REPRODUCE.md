# Reproducing the paper (fine-tuning side)

This document covers the fine-tuning results (paper Table VI phase-schema ablation, Figure 5 cross-family comparison, and Figure 6 detection-vs-proprietary) and §6.4 Findings 4–6 from the Fine-tuning Effectiveness section. The benchmark itself — Table IV (cross-scanner detection) and Table III (oracle refusal) — is reproduced from the mutation/benchmark side of this repository (`artifact/code/skillmutator/`, `claims/`).

## Pre-requisites

| Resource | Purpose |
|----------|---------|
| 1 × A100 80 GB GPU (or equivalent) | LoRA fine-tuning + vLLM inference |
| OpenAI API access (GPT-5.4 + GPT-5.4 judge) | Teacher model and evaluation judge |
| HuggingFace token (`HF_TOKEN`) | Downloading the base model weights |
| 68 community-authored skills | Training corpus (see `../../skillmutator/docs/SKILLS_SETUP.md`) |
| ~ 80 GB disk | Tokenizer + base model + LoRA checkpoints |

```bash
pip install -e .[all]          # also pulls in the skillmutator package
cp .env.example .env            # OPENAI_API_KEY, HF_TOKEN, OUTPUT_DIR, ...
export OUTPUT_DIR=$PWD/output
export DATASET_DIR=$PWD/dataset
```

## End-to-end procedure

### 1. Build the four-phase training corpus (iter_0 + iter_1 + small iter_2)

```bash
python scripts/prepare_dataset.py \
    --skills-dir <your-68-skills>/ \
    --teacher gpt-5.4 \
    --iters 0,1,2 \
    --output-dir ${DATASET_DIR}
```

Produces `train.jsonl` and `val.jsonl` under `${DATASET_DIR}`. Each example holds `messages` in OpenAI chat format with assistant content following the four-phase schema (`## Phase 1: Purpose Extraction` → `## Phase 4: Category Mapping`; these are the literal markdown section headers that the model learns to emit).

The production training corpus (basis for the 88.16 % paper headline) has the following composition:

| Field | Value |
|-------|-------|
| total samples | 1219 |
| train / val split | 1033 / 186 |
| skills covered | 68 |
| categories covered | 13 |
| iter_0 samples | 588 (48.2 %) |
| iter_1 samples | 545 (44.7 %) |
| iter_2 samples |  86 ( 7.1 %) |
| source: gpt-5.4 select-mode batch (`gpt5.4_select`) | 272 |
| source: batch1 | 497 |
| source: batch2 | 450 |

`iter_0` carries the attack's semantic structure in its clearest form, and `iter_1` carries the same attack intent re-expressed in scanner-evasion-driven phrasing; a small number of `iter_2` samples are also included.

A deterministic refine step (no LLM calls) injects ground-truth Phase 3 + Phase 4 bullets for samples whose teacher-emitted Phase 4 missed the target attack category. The refined samples are emitted into the same `train.jsonl`. See `dataset_builder/formatter_v3.py` for the exact mechanism.

### 2. Fine-tune Qwen2.5-Coder-7B-Instruct with the paper-default recipe

The dataset paths and the output directory come from the YAML config
(`training.output_dir`, `data.train_file`, `data.val_file`); edit the config
to point at your `${DATASET_DIR}` / `${OUTPUT_DIR}` before launching.

```bash
# Pre-flight smoke test (5 steps) — never skip this; see the note below.
python scripts/train.py \
    --config src/skill_scanner_finetune/finetune/configs/qwen_default.yaml \
    --max-steps 5

# Full training run
python scripts/train.py \
    --config src/skill_scanner_finetune/finetune/configs/qwen_default.yaml
```

> **Always smoke-test first.** `--max-steps 5` runs the exact training code
> path for 5 steps. Confirm the log shows `trainable: X / Y (Z%)` (LoRA wrapped
> correctly) and that the 5 step losses are finite and decreasing. This catches
> config / path / version bugs in seconds instead of hours.

Defaults match the paper:

| Hyperparameter            | Value |
|---------------------------|------:|
| Base model                | Qwen2.5-Coder-7B-Instruct (bf16, sdpa attention) |
| LoRA `r`                  | 64    |
| LoRA `alpha`              | 128   |
| LoRA `dropout`            | 0.05  |
| target modules            | q,k,v,o,gate,up,down |
| learning rate             | 5e-5  |
| LR scheduler              | cosine, warmup 0.05 |
| epochs                    | 5     |
| per-device batch size     | 1     |
| gradient accumulation     | 4     |
| effective batch size      | 4     |
| max seq length            | 16384 (32k → A100 OOM, reduced to 16k) |
| gradient checkpointing    | ON (≈30 % speed cost, memory saver) |
| quantization              | OFF (full bf16) |
| loss style                | all-token (not assistant-only) |

Training takes ~ 8 h on a single A100 80 GB.

### 3. Merge the LoRA adapter

```bash
python -m skill_scanner_finetune.finetune.merge_lora \
    --base Qwen/Qwen2.5-Coder-7B-Instruct \
    --adapter ${OUTPUT_DIR}/qwen2.5-coder-7b-finetuned/final \
    --out     ${OUTPUT_DIR}/qwen2.5-coder-7b-finetuned-merged
```

### 4. Serve via vLLM and run the scanner

```bash
# In one terminal:
vllm serve ${OUTPUT_DIR}/qwen2.5-coder-7b-finetuned-merged \
       --port 8000 --max-model-len 32768 \
       --enable-lora --max-lora-rank 64 \
       --lora-modules finetuned=${OUTPUT_DIR}/qwen2.5-coder-7b-finetuned/final \
       --gpu-memory-utilization 0.90 --dtype bfloat16

# In another terminal:
python scripts/run_scanner.py path/to/skill \
       --backend vllm --base-url http://localhost:8000/v1 \
       --model qwen2.5-coder-7b-finetuned-merged \
       --temperature 0 --frequency-penalty 0.3 \
       --prefill "## Phase 4: Category Mapping"
```

Inference defaults (vLLM 0.19.1):

| Setting | Value |
|---------|-------|
| temperature | 0 |
| frequency_penalty | 0.3 (suppresses long-output token loops) |
| max_model_len | 32768 |
| chat_template | base tokenizer default (no injection) |
| prefill string | `## Phase 4: Category Mapping\n\n` |
| prefill mechanism | assistant `continue_final_message=True` |

The `--prefill` flag injects the Phase 4 header as an assistant continuation, forcing the model to land at the verdict stage. See [docs/PIPELINE.md](PIPELINE.md) for the mechanism.

### 5. Adjudicate scanner outputs with the GPT-5.4 judge and tabulate

```bash
# Adjudicate scan outputs against the published ground truth
python -m skill_scanner_finetune.analysis.judge \
       --scan-root ${OUTPUT_DIR}/scan_full

# Build the cross-family fine-tuning comparison (paper Figure 5 / Finding 5)
python analysis/rq3/scripts/build_tab_finetune.py
```

Outputs land at `analysis/rq3/scripts/outputs/tab_finetune.{csv,tex}`. Expected (within ±2 cases of judge stochasticity, GPT-5.4 judge):

| Model                        | Base    | No-prefill    | Prefill (final)   |
|------------------------------|---------|---------------|-------------------|
| Qwen2.5-Coder-7B-Instruct    | 17.1 %  | 79.0 %        | **88.2 %**        |
| Llama-3.1-8B-Instruct        |  7.9 %  | 82.9 %        | 75.0 %            |
| Mistral-7B-Instruct-v0.3     |  5.3 %  | 72.4 %        | 55.3 %            |
| Gemma-2-9b-it                | 10.5 %  | 59.2 %        | 56.6 %            |

Only Qwen benefits from forced Phase 4 prefill; the other three families score better without it (chat-template incompatibility). See paper §6.4 Finding 5.

### 6. Phase ablation (paper Table VI / Finding 6)

For Finding 6 you re-train with a truncated phase set and re-evaluate:

| Variant                | Train data includes              | Expected detection |
|------------------------|----------------------------------|--------------------|
| P1 (no-prefill)        | only `## Phase 1`                |  1.32 %            |
| P1–2 (no-prefill)      | `## Phase 1..2`                  | 25.00 %            |
| P1–3 (no-prefill)      | `## Phase 1..3`                  | 57.89 %            |
| P1–4 (no-prefill)      | `## Phase 1..4`                  | 67.11 %            |
| + deterministic refine | full + refine                    | 78.95 %            |
| + Forced Prefix Pre-filling | full + refine + prefill (final) | **88.16 %**     |

The expected ablation table is produced by `analysis/rq4/scripts/build_tab_phase_ablation.py`; the per-variant `judge_summary.csv` files follow the same schema as the benchmark-side analysis tooling.

## Notes on inference-time prefill

The training corpus contains `## Phase 1` through `## Phase 4` markers (see `dataset_builder/formatter_v3.py`); inference forces the **same `## Phase 4: Category Mapping` heading** as the assistant continuation, eliminating the chance that small models will skip directly to free-form text. Empirically this is worth +9.2 pp on Qwen, but negative on Llama, Mistral, and Gemma (chat-template incompatibility); see paper §6.4 Finding 5 and `fig:prefill_delta_comparison`.
