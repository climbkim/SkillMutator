"""D1 train.py — same recipe as C20 (all-token loss), bypasses SFTTrainer
version churn by using plain Trainer with explicit pre-tokenization."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import yaml
import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
)


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_jsonl_messages(path: str) -> Dataset:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            records.append({"messages": obj["messages"]})
    return Dataset.from_list(records)


def make_tokenize_fn(tokenizer, max_len: int):
    def _fn(example):
        text = tokenizer.apply_chat_template(
            example["messages"], tokenize=False, add_generation_prompt=False,
        )
        enc = tokenizer(
            text,
            truncation=True,
            max_length=max_len,
            padding=False,
            add_special_tokens=False,
        )
        return {"input_ids": enc["input_ids"], "attention_mask": enc["attention_mask"]}
    return _fn


def load_tokenizer(model_name: str) -> AutoTokenizer:
    tokenizer = AutoTokenizer.from_pretrained(
        model_name, trust_remote_code=True, padding_side="right",
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    return tokenizer


def load_model(cfg: dict):
    m = cfg["model"]
    q = cfg["quantization"]
    torch_dtype = getattr(torch, m["torch_dtype"])
    bnb = None
    if q["enabled"]:
        bnb = BitsAndBytesConfig(
            load_in_4bit=q["load_in_4bit"],
            bnb_4bit_compute_dtype=getattr(torch, q["bnb_4bit_compute_dtype"]),
            bnb_4bit_use_double_quant=q["bnb_4bit_use_double_quant"],
            bnb_4bit_quant_type=q["bnb_4bit_quant_type"],
        )
    model = AutoModelForCausalLM.from_pretrained(
        m["name"],
        torch_dtype=torch_dtype,
        quantization_config=bnb,
        device_map={"": 0},
        trust_remote_code=True,
        attn_implementation=m.get("attn_implementation", "sdpa"),
    )
    if q["enabled"]:
        model = prepare_model_for_kbit_training(model)
    return model


def build_lora(cfg: dict, model):
    l = cfg["lora"]
    if not l["enabled"]:
        return model, None
    peft = LoraConfig(
        r=l["r"], lora_alpha=l["alpha"], lora_dropout=l["dropout"],
        target_modules=l["target_modules"], bias=l["bias"], task_type=l["task_type"],
    )
    model = get_peft_model(model, peft)
    return model, peft


def build_training_args(cfg: dict, max_steps: int = -1) -> TrainingArguments:
    t = cfg["training"]; l = cfg["logging"]
    # max_steps > 0 overrides num_train_epochs — used by the --max-steps smoke test.
    return TrainingArguments(
        output_dir=t["output_dir"],
        num_train_epochs=t["num_train_epochs"],
        max_steps=max_steps,
        per_device_train_batch_size=t["per_device_train_batch_size"],
        per_device_eval_batch_size=t["per_device_eval_batch_size"],
        gradient_accumulation_steps=t["gradient_accumulation_steps"],
        learning_rate=t["learning_rate"],
        lr_scheduler_type=t["lr_scheduler_type"],
        warmup_ratio=t.get("warmup_ratio", 0.05),
        weight_decay=t["weight_decay"],
        max_grad_norm=t["max_grad_norm"],
        bf16=t["bf16"], fp16=t["fp16"], tf32=t.get("tf32", False),
        gradient_checkpointing=t["gradient_checkpointing"],
        gradient_checkpointing_kwargs={"use_reentrant": False},
        dataloader_num_workers=t["dataloader_num_workers"],
        remove_unused_columns=False,
        logging_steps=l["logging_steps"],
        eval_strategy=l["eval_strategy"],
        save_strategy=l["save_strategy"],
        save_total_limit=l["save_total_limit"],
        load_best_model_at_end=l["load_best_model_at_end"],
        metric_for_best_model=l["metric_for_best_model"],
        report_to=l["report_to"],
        run_name=l["run_name"],
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--max-steps", type=int, default=-1,
                   help="Cap total training steps (overrides epochs). "
                        "Use a small value (e.g. 5) for a pre-flight smoke test.")
    args = p.parse_args()

    cfg = load_config(args.config)
    max_len = cfg["data"]["max_seq_length"]

    print(f"[1/5] tokenizer: {cfg['model']['name']}")
    tok = load_tokenizer(cfg["model"]["name"])
    tok.model_max_length = max_len

    print("[2/5] dataset load + pre-tokenize")
    dcfg = cfg["data"]
    train_ds = load_jsonl_messages(dcfg["train_file"])
    val_ds   = load_jsonl_messages(dcfg["val_file"])
    fn = make_tokenize_fn(tok, max_len)
    train_ds = train_ds.map(fn, remove_columns=["messages"], num_proc=4)
    val_ds   = val_ds.map(fn, remove_columns=["messages"], num_proc=4)
    print(f"  train: {len(train_ds)} / val: {len(val_ds)}")

    print(f"[3/5] model load (quantization={cfg['quantization']['enabled']})")
    model = load_model(cfg)
    model, _ = build_lora(cfg, model)
    train_p = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_p = sum(p.numel() for p in model.parameters())
    print(f"  trainable: {train_p:,} / {total_p:,} ({100*train_p/total_p:.2f}%)")

    print("[4/5] TrainingArguments")
    targs = build_training_args(cfg, max_steps=args.max_steps)
    if args.max_steps and args.max_steps > 0:
        print(f"  [smoke test] max_steps={args.max_steps} (epochs overridden)")
    Path(targs.output_dir).mkdir(parents=True, exist_ok=True)

    collator = DataCollatorForLanguageModeling(tokenizer=tok, mlm=False)

    print("[5/5] training start")
    trainer = Trainer(
        model=model,
        args=targs,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=collator,
        tokenizer=tok,
    )
    trainer.train(resume_from_checkpoint=args.resume or None)

    out = targs.output_dir
    print(f"\nsaving: {out}/final")
    trainer.save_model(f"{out}/final")
    tok.save_pretrained(f"{out}/final")
    print("done.")


if __name__ == "__main__":
    main()
