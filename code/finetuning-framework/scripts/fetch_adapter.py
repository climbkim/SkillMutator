"""fetch_adapter.py -- download + extract a released fine-tuned LoRA adapter.

The adapters are published on the Hugging Face Hub as one tar.gz per base model:

    climbkim/skillmutator-scanner-adapters
      Skillmutator_Scanner-Qwen2.5-Coder-7B-Instruct.tar.gz   (paper headline)
      Skillmutator_Scanner-Llama-3.1-8B-Instruct.tar.gz
      Skillmutator_Scanner-Mistral-7B-Instruct-v0.3.tar.gz
      Skillmutator_Scanner-Gemma-2-9b-it.tar.gz

This downloads the archive for one base model, extracts it, locates the PEFT
adapter directory (the folder containing `adapter_config.json`), and prints that
path on the last stdout line so run.sh can capture it for `infer.py --lora`.

Usage:
    python scripts/fetch_adapter.py \\
        --repo  climbkim/skillmutator-scanner-adapters \\
        --model Qwen2.5-Coder-7B-Instruct \\
        --out   ${OUTPUT_DIR}/adapter

`--repo` also comes from ADAPTER_REPO; `--model` from ADAPTER_MODEL.
"""
from __future__ import annotations

import argparse
import os
import sys
import tarfile
from pathlib import Path

DEFAULT_REPO = "climbkim/skillmutator-scanner-adapters"


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


def _find_adapter_dir(root: Path) -> Path | None:
    for cfg in root.rglob("adapter_config.json"):
        return cfg.parent
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Download + extract a released LoRA adapter from the Hub.")
    ap.add_argument("--repo", default=os.getenv("ADAPTER_REPO", DEFAULT_REPO),
                    help=f"HF repo id of the released adapters (default: {DEFAULT_REPO}).")
    ap.add_argument("--model", default=os.getenv("ADAPTER_MODEL", "Qwen2.5-Coder-7B-Instruct"),
                    help="Base model tag selecting Skillmutator_Scanner-<model>.tar.gz "
                         "(default: Qwen2.5-Coder-7B-Instruct).")
    ap.add_argument("--filename", default=None,
                    help="Explicit archive filename (overrides --model).")
    ap.add_argument("--revision", default=os.getenv("ADAPTER_REVISION", None),
                    help="Optional git revision / tag / commit to pin.")
    ap.add_argument("--out", required=True, help="Local directory to download + extract into.")
    args = ap.parse_args()

    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        sys.exit("[fetch_adapter] huggingface_hub not installed. Install the finetune "
                 "extras first: ./install.sh --finetune  (or pip install huggingface_hub).")

    fname = args.filename or f"Skillmutator_Scanner-{args.model}.tar.gz"
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    _log(f"[fetch_adapter] downloading {args.repo}::{fname}"
         f"{'@' + args.revision if args.revision else ''} ...")
    tar_path = hf_hub_download(repo_id=args.repo, filename=fname,
                              revision=args.revision, local_dir=str(out))

    _log(f"[fetch_adapter] extracting {Path(tar_path).name} ...")
    extract_dir = out / "extracted"
    extract_dir.mkdir(exist_ok=True)
    with tarfile.open(tar_path, "r:gz") as tf:
        tf.extractall(extract_dir)

    adapter_dir = _find_adapter_dir(extract_dir)
    if adapter_dir is None:
        sys.exit(f"[fetch_adapter] no adapter_config.json found under {extract_dir}; "
                 f"inspect the archive contents.")

    _log(f"[fetch_adapter] adapter ready: {adapter_dir}")
    # last stdout line = the adapter dir path (run.sh captures this)
    print(str(adapter_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
