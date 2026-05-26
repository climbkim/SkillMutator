"""scanner_finetune.py -- fine-tuned scanner variant of the baseline scanner.

Differs from the baseline scanner in two places:

1. **System prompt injection.** The fine-tuned model was trained with a
   system+user chat layout that mentions the 4-Phase analysis schema. We
   prepend the same system message to every call.
2. **Forced Prefix Pre-filling.** We append an `assistant` turn whose content
   is exactly the canonical heading of the final phase
   (`## Phase 4: Category Mapping`), then turn on vLLM's
   `continue_final_message=True` extension so the server treats the assistant
   turn as a continuation rather than starting a new turn. The model is
   thereby forced to land at the categorical verdict stage instead of
   regenerating Phases 1-3 at inference time.

   This prefill is a vLLM extension; raw OpenAI ignores it. When the
   endpoint rejects the extension we fall back to a plain call (no prefill).

Usage:
    python -m skill_scanner_finetune.scanner.scanner_finetune \\
        -p openai -s skills/pdf -m /path/to/merged_model \\
        -u http://localhost:8000/v1 -o /tmp/out -t 12000

The Phase 4 heading must match the marker emitted by
`dataset_builder/formatter_v3.py`. Keep them in sync if the schema is changed.
"""

import argparse
import os
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR))

import scanner_base as base  # noqa: E402


# ----------------------------------------------------------------------
# System prompt for the fine-tuned model -- describes the 4-Phase schema
# (must match the prompt used during training; see formatter_v3.py).
# ----------------------------------------------------------------------
FT_SYSTEM_PROMPT = (
    "You are an expert AI agent security analyst specializing in LLM-powered agent skill security. "
    "Your task is to analyze agent skills -- composed of SKILL.md instruction documents and Python helper "
    "scripts -- and produce a structured 4-Phase security analysis. "
    "Reason step-by-step, cite specific file locations and code patterns as evidence, "
    "and distinguish what a skill claims to do versus what it actually does. "
    "Your final output must list security findings with attack categories."
)

# Canonical Forced Prefix Pre-filling heading. Must match the final phase
# marker emitted by dataset_builder/formatter_v3.py
# (## Phase 4: Category Mapping).
PHASE4_PREFIX = "## Phase 4: Category Mapping\n\n\n"


# ----------------------------------------------------------------------
# Monkey-patch the baseline scanner's _call_openai to use prefilling.
#
# Original signature:
#     _call_openai(client, model_name, prompt: str, use_reasoning) -> dict
#     -- internally builds messages = [{"role":"user","content":prompt}].
#
# New behavior:
#     1. messages = [system, user(prompt), assistant(PHASE4_PREFIX)]
#     2. enable vLLM continue_final_message via extra_body
#     3. prepend PHASE4_PREFIX to the response so the saved markdown still
#        carries the Phase 4 heading.
# ----------------------------------------------------------------------
def _call_openai_finetune(client, model_name: str, messages_or_prompt, use_reasoning: bool) -> dict:
    """Call the OpenAI-compatible API with vLLM assistant prefill enabled.

    Depending on the baseline scanner version `messages_or_prompt` may be:
    - str (older): the raw user prompt
    - list (newer): a [system, user] messages list
    """
    if isinstance(messages_or_prompt, list):
        # Newer scanner: extract the user message content from the list.
        user_content = ""
        for m in messages_or_prompt:
            if m.get("role") == "user":
                user_content = m.get("content", "")
                break
        prompt = user_content
    else:
        prompt = messages_or_prompt

    messages = [
        {"role": "system",    "content": FT_SYSTEM_PROMPT},
        {"role": "user",      "content": prompt},
        {"role": "assistant", "content": PHASE4_PREFIX},
    ]
    extra = {"continue_final_message": True, "add_generation_prompt": False}

    try:
        if use_reasoning:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                reasoning_effort="medium",
                extra_body=extra,
            )
        else:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.0,  # deterministic, matches training-time inference
                extra_body=extra,
            )
    except Exception as e:
        err = str(e).lower()
        if "temperature" in err and "unsupported" in err:
            print(f"\n    [!] Model '{model_name}' does not support temperature; using default.")
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                extra_body=extra,
            )
        elif "extra_body" in err or "continue_final_message" in err or "unexpected keyword" in err:
            # Endpoint does not support assistant prefilling -- fall back
            # to a plain call without the prefill turn.
            print(f"\n    [!] Endpoint does not support assistant prefill; falling back without it.")
            messages_fallback = messages[:-1]  # drop the assistant prefill turn
            response = client.chat.completions.create(
                model=model_name,
                messages=messages_fallback,
                temperature=0.0,
            )
        else:
            raise

    usage = response.usage
    raw = response.choices[0].message.content or ""
    # Restore the prefix in the saved markdown so the final report carries
    # the canonical Phase 4 heading.
    content = PHASE4_PREFIX + raw
    return {
        "content":           content,
        "prompt_tokens":     usage.prompt_tokens if usage else 0,
        "completion_tokens": usage.completion_tokens if usage else 0,
        "total_tokens":      usage.total_tokens if usage else 0,
    }


# Replace the baseline _call_openai with the fine-tuned variant.
base._call_openai = _call_openai_finetune


# ----------------------------------------------------------------------
# CLI -- mirrors the baseline scanner.
# ----------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Agent Skill Vulnerability Scanner -- fine-tuned variant"
    )
    parser.add_argument("-s", "--skill", type=str)
    parser.add_argument("-p", "--provider", type=str, choices=base.SUPPORTED_PROVIDERS)
    parser.add_argument("-m", "--model", type=str)
    parser.add_argument("-r", "--reasoning", action="store_true")
    parser.add_argument("-o", "--output-dir", type=str, default=None)
    parser.add_argument("-u", "--base-url", type=str, default=None)
    parser.add_argument("-t", "--max-tokens", type=int, default=None)

    args = parser.parse_args()
    use_reasoning = args.reasoning

    provider = args.provider
    if not provider:
        print("-" * 50)
        print(f"[?] Choose an LLM provider: {base.SUPPORTED_PROVIDERS}")
        provider = input("    > ").strip().lower()
        if provider not in base.SUPPORTED_PROVIDERS:
            print(f"[error] Unsupported provider: {provider}")
            sys.exit(1)

    if args.model:
        model_name = args.model
    else:
        model_name = (base.DEFAULT_REASONING_MODELS[provider] if use_reasoning
                      else base.DEFAULT_MODELS[provider])

    skill_name = args.skill
    if not skill_name:
        print("-" * 50)
        skill_name = input("[?] Enter the agent-skill folder to analyze: ").strip()

    if os.path.isabs(skill_name) or (os.path.sep in skill_name) or ("/" in skill_name):
        target_directory = skill_name
        display_name = os.path.basename(skill_name.rstrip("/\\"))
    else:
        target_directory = os.path.join(os.getcwd(), "skills", skill_name)
        display_name = skill_name

    print("-" * 50)
    if not skill_name:
        print("[error] no folder name provided.")
    elif os.path.isdir(target_directory):
        client = base.create_client(provider, base_url=args.base_url)
        base.evaluate_agent_skills(
            client, provider, target_directory, display_name, model_name,
            use_reasoning, args.output_dir, max_input_tokens=args.max_tokens,
        )
    else:
        print(f"\n[error] Path not found: {target_directory}")
