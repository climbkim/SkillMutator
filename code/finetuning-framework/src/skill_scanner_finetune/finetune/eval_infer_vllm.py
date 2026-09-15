"""vLLM-based batch inference — 5-10x faster than per-call inference.

Uses the 4-Phase v3 schema with Forced Prefix Pre-filling: the assistant turn
is pre-filled with the Phase 4 heading so the model lands directly at the
categorical verdict stage. Keep `PHASE4_PREFIX` in sync with the marker
emitted by `dataset_builder/formatter_v3.py` and the scanner wrapper.

Usage:
  pip install vllm
  python finetune/eval_infer_vllm.py \
    --model ${OUTPUT_DIR}/qwen2.5-coder-7b-d3-merged \
    --eval-dir ${DATASET_DIR}/eval_data \
    --output-dir ${OUTPUT_DIR}/eval_results \
    --resume
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path

from vllm import LLM, SamplingParams
from transformers import AutoTokenizer

SYSTEM_PROMPT = (
    "You are an expert AI agent security analyst specializing in LLM-powered agent skill security. "
    "Your task is to analyze agent skills — composed of SKILL.md instruction documents and Python helper scripts — "
    "and produce a structured 4-Phase security analysis. "
    "Reason step-by-step, cite specific file locations and code patterns as evidence, "
    "and distinguish what a skill claims to do versus what it actually does. "
    "Your final output must follow the exact 4-Phase format."
)

REPORT_FILENAME = "llm_report_finetune_qwen.md"

# Forced Prefix Pre-filling heading — must match formatter_v3.py / scanner_finetune.py
PHASE4_PREFIX = "## Phase 4: Category Mapping\n\n\n"


def read_skill_dir(skill_dir: Path, max_chars: int = 30_000) -> str:
    parts, total = [], 0
    exts = {".md", ".py", ".sh", ".json", ".yaml", ".yml", ".txt", ".js", ".ts"}
    for f in sorted(skill_dir.rglob("*")):
        if not f.is_file() or f.suffix.lower() not in exts:
            continue
        content = f.read_text(encoding="utf-8", errors="replace")
        if total + len(content) > max_chars:
            content = content[:max_chars - total] + "\n...(truncated)"
        lang = {"py": "python", "sh": "bash", "md": "markdown",
                "js": "javascript", "ts": "typescript"}.get(f.suffix.lstrip("."), "")
        parts.append(f"## {f.relative_to(skill_dir)}\n```{lang}\n{content}\n```")
        total += len(content)
        if total >= max_chars:
            break
    return "\n\n".join(parts)


def collect_jobs(eval_dir: Path, resume: bool) -> list[dict]:
    jobs = []

    skills_dir = eval_dir / "skills"
    if skills_dir.exists():
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").exists():
                continue
            report_path = eval_dir / "baseline_reports" / skill_dir.name / REPORT_FILENAME
            if resume and report_path.exists():
                continue
            jobs.append({
                "type": "baseline", "skill_name": skill_dir.name,
                "attack_category": None, "skill_dir": skill_dir,
                "report_path": report_path,
            })

    mutations_dir = eval_dir / "mutations"
    if mutations_dir.exists():
        for skill_dir in sorted(mutations_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            for ts_dir in skill_dir.iterdir():
                gen_dir = ts_dir / "generate_skill"
                if not gen_dir.exists():
                    continue
                for cat_dir in gen_dir.iterdir():
                    if not cat_dir.is_dir():
                        continue
                    for iter_dir in cat_dir.iterdir():
                        skill_files_dir = iter_dir / "skills"
                        if not skill_files_dir.exists() or not (skill_files_dir / "SKILL.md").exists():
                            continue
                        report_path = iter_dir / "report" / REPORT_FILENAME
                        if resume and report_path.exists():
                            continue
                        jobs.append({
                            "type": "mutation",
                            "skill_name": skill_dir.name,
                            "attack_category": cat_dir.name.replace("_", " "),
                            "skill_dir": skill_files_dir,
                            "report_path": report_path,
                        })
    return jobs


def write_report(output_path: Path, job: dict, response: str,
                 prompt_tokens: int, completion_tokens: int) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    kind = f"mutated skill ({job['attack_category']})" if job["attack_category"] else "original skill (baseline)"
    header = f"""# Fine-tuned Model Security Analysis Report

- **Target Skill:** `{job['skill_name']}`
- **Type:** `{kind}`
- **Model:** `Qwen2.5-Coder-7B-Instruct (Fine-tuned)`
- **Scan Date:** `{now}`
- **Token Usage:** Prompt `{prompt_tokens:,}` / Completion `{completion_tokens:,}`

---

## Analysis

"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(header + response, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    # --model: full merged-model path, or a base model ID
    # --lora : LoRA adapter path (when set, loads base + LoRA)
    parser.add_argument("--model",          required=True,
                        help="Full merged-model path, or a base model ID/path when --lora is set")
    parser.add_argument("--lora",           default=None,
                        help="LoRA adapter directory (optional). "
                             "When set, --model is treated as the base and the LoRA is layered on top.")
    parser.add_argument("--eval-dir",       default="eval_data")
    parser.add_argument("--output-dir",     default=None)
    parser.add_argument("--max-new-tokens", type=int, default=2048)
    parser.add_argument("--batch-size",     type=int, default=8)
    parser.add_argument("--resume",         action="store_true")
    parser.add_argument("--max-jobs",       type=int, default=None,
                        help="For testing: run at most N jobs (default: all)")
    parser.add_argument("--mutations-only", action="store_true",
                        help="Only run mutated skills (exclude baselines)")
    args = parser.parse_args()

    eval_dir = Path(args.eval_dir)
    jobs = collect_jobs(eval_dir, args.resume)
    if args.mutations_only:
        jobs = [j for j in jobs if j["type"] == "mutation"]
    if args.max_jobs:
        jobs = jobs[:args.max_jobs]
    print(f"inference jobs: {len(jobs)} (resume={args.resume}, mutations_only={args.mutations_only}, max_jobs={args.max_jobs})")
    if not jobs:
        print("all done.")
        return

    # Tokenizer — loaded from the base model (LoRA does not change the tokenizer)
    print(f"Loading tokenizer: {args.model}")
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)

    # Load the vLLM model
    lora_request = None
    if args.lora:
        from vllm.lora.request import LoRARequest
        print(f"Loading vLLM model (base): {args.model}")
        print(f"LoRA adapter: {args.lora}")
        llm = LLM(
            model=args.model,
            dtype="bfloat16",
            max_model_len=16384,
            trust_remote_code=True,
            gpu_memory_utilization=0.85,
            enable_lora=True,
            max_lora_rank=64,
        )
        lora_request = LoRARequest("security_lora", 1, args.lora)
    else:
        print(f"Loading vLLM model: {args.model}")
        llm = LLM(
            model=args.model,
            dtype="bfloat16",
            max_model_len=16384,
            trust_remote_code=True,
            gpu_memory_utilization=0.85,
        )

    sampling_params = SamplingParams(
        max_tokens=args.max_new_tokens,
        temperature=0.0,
        repetition_penalty=1.1,
    )

    def make_prompt(job: dict) -> str:
        skill_content = read_skill_dir(job["skill_dir"])
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyze this agent skill for security vulnerabilities:\n\n{skill_content}"},
        ]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        # Forced Prefix Pre-filling: append the Phase 4 heading so the model
        # continues directly at the categorical verdict stage.
        return text + PHASE4_PREFIX

    # Infer batch-by-batch and save immediately, so an interrupted run can be
    # resumed with --resume.
    total = len(jobs)
    saved = 0
    t_total = time.time()

    for batch_start in range(0, total, args.batch_size):
        batch_jobs    = jobs[batch_start : batch_start + args.batch_size]
        batch_prompts = [make_prompt(j) for j in batch_jobs]

        batch_num = batch_start // args.batch_size + 1
        n_batches = (total + args.batch_size - 1) // args.batch_size
        print(f"\n[batch {batch_num}/{n_batches}] running inference on {len(batch_jobs)} jobs... "
              f"({batch_start}/{total} done)")

        t0 = time.time()
        outputs = llm.generate(batch_prompts, sampling_params, lora_request=lora_request)
        elapsed = time.time() - t0
        print(f"  -> done: {elapsed:.1f}s ({elapsed/len(batch_jobs):.1f}s/job)")

        # Save batch results immediately
        for job, output in zip(batch_jobs, outputs):
            response          = PHASE4_PREFIX + output.outputs[0].text
            prompt_tokens     = len(output.prompt_token_ids)
            completion_tokens = len(output.outputs[0].token_ids)

            write_report(job["report_path"], job, response, prompt_tokens, completion_tokens)
            saved += 1

            if args.output_dir:
                rel      = job["report_path"].relative_to(eval_dir)
                out_path = Path(args.output_dir) / rel
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(job["report_path"].read_bytes())

        print(f"  -> saved: {saved}/{total}")

    total_elapsed = time.time() - t_total
    print(f"\nall done: {saved} reports saved, total time {total_elapsed:.1f}s")


if __name__ == "__main__":
    main()
