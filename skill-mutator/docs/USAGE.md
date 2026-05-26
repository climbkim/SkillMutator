# Using skill-mutator on your own skills

This document shows how to apply `skill-mutator` outside the paper's benchmark — e.g. to red-team a private skill marketplace or to evaluate a custom scanner.

## Mutating a single skill

```bash
python scripts/run_mutation.py path/to/your-skill \
    --provider openai --model gpt-5.4-mini \
    --mode select \
    --max-iters 5 \
    --result-dir ./results/my-eval
```

Outputs land at `./results/my-eval/<your-skill>/<timestamp>/generate_skill/<attack_category>/iter_K/`.

The mutation pipeline injects a directive corresponding to one of 13 attack categories (see `docs/attack_categories.json`) into the SKILL.md and accompanying scripts, then iteratively refines the injection to evade scanner feedback.

## Scanning a (mutated or original) skill

```bash
# Rule-based SAST
python scripts/run_scanner.py path/to/skill --scanner skill-security

# Snyk Agent Scan
python scripts/run_scanner.py path/to/skill --scanner snyk

# LLM-based
python scripts/run_scanner.py path/to/skill --scanner llm \
    --provider openai --model gpt-5.4-mini
```

Each scanner writes a structured `verdict.json` next to its raw report.

## Plugging in a custom scanner

`src/skill_mutator/scanners/llm_scanner/scanner.py` is a thin OpenAI-compatible wrapper. To swap in a different scanner backend (for example, your locally fine-tuned model from the sister repo `skill-scanner-finetune`), point the `--base-url` flag at any OpenAI-compatible endpoint:

```bash
python scripts/run_scanner.py path/to/skill --scanner llm \
    --provider openai \
    --base-url http://localhost:8000/v1 \
    --model my-finetuned-scanner
```

The wrapper uses the standard OpenAI Python SDK, so any vLLM / sglang / TGI server works out of the box.

## Using the GPT-5.4 v2 judge in your own pipeline

`analysis/skillmutator_utils/judge.py` exposes:

```python
from skillmutator_utils.judge import judge_call

verdict = judge_call(
    skill="my-skill",
    category="Information Gathering",
    title="(your-scenario-title)",
    disguise="",
    injected_snippet="(the malicious content you injected)",
    scan_text="(the scanner's raw output)",
)
# -> {"detected": True/False, "confidence": 0.0..1.0, "reason": "..."}
```

This is the same judge used to produce every LLM-scanner verdict in Table 1 of the paper.

## Environment variables

| Variable                 | Default                     | Purpose                                  |
|--------------------------|-----------------------------|------------------------------------------|
| `OPENAI_API_KEY`         | —                           | required for the LLM scanner / judge     |
| `ANTHROPIC_API_KEY`      | —                           | optional (Anthropic-backed mutation)     |
| `GOOGLE_API_KEY`         | —                           | optional (Gemini-backed mutation)        |
| `SNYK_TOKEN`             | —                           | optional (Snyk Agent Scan)               |
| `HF_TOKEN`               | —                           | optional (HuggingFace-served scanners)   |
| `HF_ENDPOINT_URL`        | placeholder                 | dedicated HF endpoint URL (override)     |
| `SKILL_MUTATOR_DATA_DIR` | `./data`                    | top-level output root for runs           |
| `SKILLMUTATOR_DATA_ROOT` | `./data/skillmutator-data`  | unified data tree (read by `analysis/`)  |
