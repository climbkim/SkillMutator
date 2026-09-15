"""Run skill-security analysis inference with a fine-tuned model.

Usage:
  # With a LoRA adapter (before merging)
  python infer.py --base Qwen/Qwen2.5-Coder-7B-Instruct \
                  --lora output/qwen2.5-coder-7b-d3/final \
                  --skill ../skills/admapix

  # With a merged model
  python infer.py --model output/qwen2.5-coder-7b-d3-merged --skill ../skills/admapix
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


SYSTEM_PROMPT = (
    "You are an expert AI agent security analyst specializing in LLM-powered agent skill security. "
    "Your task is to analyze agent skills — composed of SKILL.md instruction documents and Python helper scripts — "
    "and produce a structured 4-Phase security analysis. "
    "Reason step-by-step, cite specific file locations and code patterns as evidence, "
    "and distinguish what a skill claims to do versus what it actually does. "
    "Your final output must follow the exact 4-Phase format."
)


def read_skill_dir(skill_dir: Path) -> str:
    """Format the files in a skill directory into a single prompt string."""
    parts = []
    for f in sorted(skill_dir.rglob("*")):
        if f.is_file() and f.suffix in (".md", ".py", ".sh", ".json", ".yaml", ".yml", ".txt"):
            rel = f.relative_to(skill_dir)
            content = f.read_text(encoding="utf-8", errors="replace")
            lang = {"py": "python", "sh": "bash", "md": "markdown"}.get(f.suffix.lstrip("."), "")
            parts.append(f"## {rel}\n```{lang}\n{content}\n```")
    return "\n\n".join(parts)


def _from_pretrained_bf16(path: str):
    """Load a causal LM in bf16 across transformers versions.

    transformers >=5 renamed the `torch_dtype` argument to `dtype`; 4.x still
    expects `torch_dtype`. Try the new name, fall back to the old one so the
    same code runs on both.
    """
    common = dict(device_map="auto", trust_remote_code=True)
    try:
        return AutoModelForCausalLM.from_pretrained(path, dtype=torch.bfloat16, **common)
    except TypeError:
        return AutoModelForCausalLM.from_pretrained(path, torch_dtype=torch.bfloat16, **common)


def load_model_and_tokenizer(base: str | None, lora: str | None, model: str | None):
    if model:
        print(f"Loading model: {model}")
        tokenizer = AutoTokenizer.from_pretrained(model, trust_remote_code=True)
        return _from_pretrained_bf16(model), tokenizer

    from peft import PeftModel
    print(f"Loading base: {base}")
    tokenizer = AutoTokenizer.from_pretrained(base, trust_remote_code=True)
    m = _from_pretrained_bf16(base)
    if lora:
        print(f"Loading LoRA: {lora}")
        m = PeftModel.from_pretrained(m, lora)
    return m, tokenizer


def run_inference(model, tokenizer, skill_content: str, cfg: dict) -> str:
    user_content = f"Analyze this agent skill for security vulnerabilities:\n\n{skill_content}"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    try:
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    except Exception:
        # Some chat templates (e.g. Gemma) don't support a `system` role — fold the
        # system prompt into the user turn so the same code path works everywhere.
        merged = [{"role": "user", "content": SYSTEM_PROMPT + "\n\n" + user_content}]
        text = tokenizer.apply_chat_template(merged, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=cfg.get("max_new_tokens", 4096),
            temperature=cfg.get("temperature", 0.1),
            do_sample=cfg.get("do_sample", False),
            pad_token_id=tokenizer.eos_token_id,
        )

    generated = outputs[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(generated, skip_special_tokens=True)


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--model", help="Path to a merged model")
    group.add_argument("--base",  help="Base model (use together with --lora)")
    parser.add_argument("--lora",  help="LoRA adapter path")
    parser.add_argument("--skill", required=True, help="Skill directory to analyze")
    parser.add_argument("--max-new-tokens", type=int, default=4096)
    args = parser.parse_args()

    if not args.model and not args.base:
        parser.error("set one of --model or --base.")

    skill_dir = Path(args.skill)
    if not skill_dir.exists():
        print(f"skill directory not found: {skill_dir}", file=sys.stderr)
        sys.exit(1)

    model, tokenizer = load_model_and_tokenizer(args.base, args.lora, args.model)
    skill_content = read_skill_dir(skill_dir)

    print(f"\n{'='*60}")
    print(f"Analyzing: {skill_dir.name}")
    print(f"{'='*60}\n")

    result = run_inference(model, tokenizer, skill_content, {"max_new_tokens": args.max_new_tokens})
    print(result)


if __name__ == "__main__":
    main()
