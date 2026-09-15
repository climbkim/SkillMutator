# Using the fine-tuned scanner on your own skills

This document covers the *deployer* path: you have a trained LoRA adapter (either re-created via [REPRODUCE.md](REPRODUCE.md) or your own) and want to scan skills with it.

## Serving the adapter via vLLM

Merge the adapter once, then serve it with vLLM:

```bash
python -m skill_scanner_finetune.finetune.merge_lora \
       --base    Qwen/Qwen2.5-Coder-7B-Instruct \
       --adapter ${OUTPUT_DIR}/qwen2.5-coder-7b-d3/final \
       --out     ${OUTPUT_DIR}/qwen2.5-coder-7b-d3-merged

vllm serve ${OUTPUT_DIR}/qwen2.5-coder-7b-d3-merged \
       --port 8000 --max-model-len 32768
```

vLLM exposes an OpenAI-compatible API on `http://localhost:8000/v1`.

## Scanning a skill

```bash
python scripts/run_scanner.py path/to/your-skill \
       --backend vllm \
       --base-url http://localhost:8000/v1 \
       --model qwen2.5-coder-7b-d3-merged \
       --prefill "## Phase 4: Category Mapping"
```

The output is a Markdown report with the four phases. The final phase (`## Phase 4: Category Mapping`) lists one or more attack categories from the 13-category taxonomy, with bullet evidence per category.

## Scoring against ground truth (offline, with the v2 judge)

If you happen to know which attack category was injected (e.g. you mutated the skill yourself with the sister `skill-mutator` package), you can score the scanner's output deterministically:

```python
from skill_scanner_finetune.analysis.judge import judge_call

verdict = judge_call(
    skill="my-skill",
    category="Information Gathering",
    title="...",
    disguise="",
    injected_snippet=open("injected_content.md").read(),
    scan_text=open("scan.md").read(),
)
print(verdict)   # {"detected": True, "confidence": 0.97, "reason": "..."}
```

This is the same GPT-5.4 v2 judge used to produce every detection number in the paper.

## Without prefilling (simpler but lower recall)

If you do not have a vLLM-style "continue_final_message" extension on your inference backend, drop `--prefill`:

```bash
python scripts/run_scanner.py path/to/your-skill \
       --backend openai-compat \
       --base-url <your-endpoint>/v1 \
       --model my-finetuned-scanner
```

Prefill is model-dependent (paper §6.4 Finding 5, `fig:prefill_delta_comparison`). Only Qwen benefits from forced Phase-4 prefill (+9.2 pp under the GPT-5.4 judge); Llama, Mistral, and Gemma score *higher* without it — dropping prefill changes detection by roughly +7.9 / +17.1 / +2.6 pp for Llama / Mistral / Gemma, due to chat-template incompatibilities. Pick the variant that matches your base model.

## Environment variables

| Variable        | Purpose                                          |
|-----------------|--------------------------------------------------|
| `OPENAI_API_KEY`| Required for the v2 judge (analysis path)        |
| `HF_TOKEN`      | HuggingFace base-model downloads                 |
| `OUTPUT_DIR`    | Where the trainer writes checkpoints + merged    |
| `DATASET_DIR`   | Where `prepare_dataset.py` writes `train.jsonl`  |
| `VLLM_BASE_URL` | Default vLLM endpoint (defaults to localhost)    |
