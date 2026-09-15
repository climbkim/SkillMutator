# Pipeline: four-phase analysis schema and Forced Prefix Pre-filling

## The four-phase schema

A skill is assessed in four sequential phases, each producing a structured artifact that the next phase consumes. Both training data and inference outputs follow the same schema. The literal markdown section headers (e.g., `## Phase 4: Category Mapping`) are the canonical strings the model emits, and the display names follow the paper:

| Phase | Display name (paper)         | Markdown section header (training/inference) | Output format |
|-------|------------------------------|----------------------------------------------|---------------|
| 1     | Purpose Grounding            | `## Phase 1: Purpose Extraction`             | JSON          |
| 2     | Out-of-Scope Detection       | `## Phase 2: Added-Scope Enumeration`        | JSON          |
| 3     | Security Principle Reasoning | `## Phase 3: Principle Violations`           | Markdown      |
| 4     | Attack Category Labeling     | `## Phase 4: Category Mapping`               | Markdown      |

`Phase 1` and `Phase 2` are JSON code blocks; `Phase 3` and `Phase 4` are free-form Markdown. The category vocabulary in Phase 4 is fixed at 13 attack categories plus an `Uncategorized` escape hatch.

## Forced Prefix Pre-filling at inference

Small open-source models (7B–9B class) often abandon the schema before reaching `Phase 4` — they spend their generation budget on Phase 2 / Phase 3 narrative and never land at the categorical verdict. To force completion, the inference wrapper injects the `Phase 4` header as an **assistant continuation**:

```python
# Conceptual pseudocode (see scanner/scanner_finetune.py for the real implementation)
messages = [
    {"role": "system",    "content": SYSTEM_PROMPT},
    {"role": "user",      "content": SKILL_PROMPT},
    {"role": "assistant", "content": "## Phase 4: Category Mapping\n\n"},
]
client.chat.completions.create(
    model=model,
    messages=messages,
    extra_body={
        "continue_final_message": True,    # vLLM-specific
        "add_generation_prompt": False,
    },
)
```

The `continue_final_message` option is a vLLM extension; it tells the server to **continue** writing from the assistant content the client already provided, rather than starting a new turn. The model thus emits only the Phase 4 verdict, conditioned on a Phase 1–2 prefix it never had to generate explicitly.

### Why this works

The fine-tuned model has seen tens of thousands of training tokens that follow the pattern `... ## Phase 3: ... ## Phase 4: Category Mapping ...`. Forcing the `Phase 4` header at the start of its generation places it at exactly the same conditional context the verdict head was trained on, while skipping the cumulative latency cost of regenerating Phases 1–3 at inference.

### Caveats

- **vLLM-specific.** Raw OpenAI chat completions ignore `continue_final_message` and treat the assistant content as just another conversation turn. Hosted inference platforms typically need a wrapper.
- **Chat-template fragility.** Models with strict role validation (e.g. Gemma-2 disallowing `system`) may strip or reject the assistant prefix. In our experiments the prefill produces +9.2 pp on Qwen, −7.9 pp on Llama, −17.1 pp on Mistral, and −2.6 pp on Gemma; see paper Finding 5 (§6.4, fig:prefill_delta_comparison) and Table VI.
- **Out-of-distribution prefixes are dangerous.** If you change the wording of the forced prefix between training and inference, the model is conditioned on a context it has never seen. The included default `"## Phase 4: Category Mapping\n\n"` matches the marker emitted by `dataset_builder/formatter_v3.py`. Keep them in sync.

## Where this lives in the code

| File                                                | Role                                          |
|-----------------------------------------------------|-----------------------------------------------|
| `src/skill_scanner_finetune/dataset_builder/formatter_v3.py` | Builds four-phase JSONL training data         |
| `src/skill_scanner_finetune/analysis_phases/`        | Phase prompt templates (one file per phase)   |
| `src/skill_scanner_finetune/scanner/scanner_finetune.py` | Inference wrapper + Forced Prefix Pre-filling |
| `src/skill_scanner_finetune/finetune/train.py`       | TRL/PEFT training entry point                 |
