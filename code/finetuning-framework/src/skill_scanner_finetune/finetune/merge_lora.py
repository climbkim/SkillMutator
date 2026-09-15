"""Merge a LoRA adapter into its base model and save a single merged model.

Usage:
  python merge_lora.py \
    --base  Qwen/Qwen2.5-Coder-7B-Instruct \
    --lora  output/qwen2.5-coder-7b-d3/final \
    --out   output/qwen2.5-coder-7b-d3-merged
"""

import argparse
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True, help="Base model path or HF Hub ID")
    parser.add_argument("--lora", required=True, help="LoRA adapter directory")
    parser.add_argument("--out",  required=True, help="Output path for the merged model")
    parser.add_argument("--dtype", default="bfloat16")
    args = parser.parse_args()

    dtype = getattr(torch, args.dtype)
    print(f"Loading base model: {args.base}")
    base = AutoModelForCausalLM.from_pretrained(
        args.base,
        dtype=dtype,
        device_map="auto",
        trust_remote_code=True,
    )

    print(f"Loading LoRA adapter: {args.lora}")
    model = PeftModel.from_pretrained(base, args.lora)

    print("Merging...")
    model = model.merge_and_unload()

    print(f"Saving: {args.out}")
    model.save_pretrained(args.out, safe_serialization=True)
    AutoTokenizer.from_pretrained(args.base, trust_remote_code=True).save_pretrained(args.out)
    print("done.")


if __name__ == "__main__":
    main()
