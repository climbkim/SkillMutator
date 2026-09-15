"""run_scanner.py -- thin CLI wrapper around scanner_finetune.

Equivalent to `python -m skill_scanner_finetune.scanner.scanner_finetune`,
but with friendlier flag names and a single positional argument.

Usage:
    # With Forced Prefix Pre-filling (default; the paper's setting)
    python scripts/run_scanner.py path/to/skill \\
        --backend vllm \\
        --base-url http://localhost:8000/v1 \\
        --model qwen2.5-coder-7b-d3-merged

    # Without prefilling (smaller recall on Qwen/Llama, slightly higher on
    # Mistral/Gemma -- see docs/PIPELINE.md)
    python scripts/run_scanner.py path/to/skill \\
        --backend openai-compat \\
        --base-url http://localhost:8000/v1 \\
        --model qwen2.5-coder-7b-d3-merged \\
        --no-prefill
"""
from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the fine-tuned scanner against a skill folder.")
    ap.add_argument("skill_path", help="Path to a skill folder (must contain SKILL.md).")
    ap.add_argument("--backend", choices=["vllm", "openai-compat"], default="vllm",
                    help="Inference backend. 'vllm' enables Forced Prefix Pre-filling.")
    ap.add_argument("-u", "--base-url", default=None,
                    help="OpenAI-compatible endpoint (e.g. http://localhost:8000/v1).")
    ap.add_argument("-m", "--model", required=True,
                    help="Model id served by the endpoint.")
    ap.add_argument("--prefill", default="## Phase 4: Category Mapping",
                    help="Forced Prefix Pre-filling heading. Must match the corpus marker.")
    ap.add_argument("--no-prefill", action="store_true",
                    help="Disable Forced Prefix Pre-filling (falls back to a plain call).")
    ap.add_argument("-o", "--output-dir", default=None,
                    help="Where to write the scan report.")
    ap.add_argument("-t", "--max-tokens", type=int, default=None,
                    help="Override the per-call token cap.")
    ap.add_argument("--temperature", type=float, default=0.0,
                    help="Sampling temperature (default 0).")
    ap.add_argument("--frequency-penalty", type=float, default=0.3,
                    help="vLLM frequency_penalty (default 0.3, suppresses long loops).")
    args = ap.parse_args()

    scanner_py = (Path(__file__).resolve().parent.parent / "src"
                  / "skill_scanner_finetune" / "scanner" / "scanner_finetune.py")
    if not scanner_py.is_file():
        sys.exit(f"[error] scanner not found at {scanner_py}")

    # Reshape into the underlying script's CLI.
    fwd = [str(scanner_py),
           "-p", "openai", "-s", str(Path(args.skill_path).resolve()),
           "-m", args.model]
    if args.base_url:   fwd += ["-u", args.base_url]
    if args.output_dir: fwd += ["-o", args.output_dir]
    if args.max_tokens: fwd += ["-t", str(args.max_tokens)]
    if args.no_prefill: fwd += ["--no-prefill"]
    if args.prefill and not args.no_prefill:
        fwd += ["--prefill", args.prefill]

    sys.argv = fwd
    runpy.run_path(str(scanner_py), run_name="__main__")
    return 0


if __name__ == "__main__":
    sys.exit(main())