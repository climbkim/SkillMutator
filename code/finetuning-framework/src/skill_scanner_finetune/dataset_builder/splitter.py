"""Stratified train/val/test split for the JSONL dataset."""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path


def split_dataset(
    raw_dir: Path,
    combined_dir: Path,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    seed: int = 42,
) -> dict:
    """Split dataset/raw/*.jsonl into dataset/combined/{full,train,val,test}.jsonl.

    Stratified on `is_malicious`, so the malicious / benign ratio is preserved
    in every split.

    Returns:
        {"train": N, "val": N, "test": N, "total": N}
    """
    random.seed(seed)
    combined_dir.mkdir(parents=True, exist_ok=True)

    # Read every raw JSONL file.
    all_entries: list[dict] = []
    for jsonl_path in sorted(raw_dir.glob("*.jsonl")):
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    all_entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if not all_entries:
        print("[WARN] no data found in the raw/ directory.")
        return {"train": 0, "val": 0, "test": 0, "total": 0}

    # Stratify on is_malicious; split each group by ratio.
    groups: dict[bool, list[dict]] = defaultdict(list)
    for entry in all_entries:
        meta = entry.get("metadata", {})
        groups[bool(meta.get("is_malicious", False))].append(entry)

    train_entries: list[dict] = []
    val_entries: list[dict] = []
    test_entries: list[dict] = []

    for is_mal, group in groups.items():
        random.shuffle(group)
        n = len(group)
        n_train = max(1, round(n * train_ratio))
        n_val = max(1, round(n * val_ratio)) if n >= 3 else 0
        # If n is too small, the test split may end up empty.
        n_test = n - n_train - n_val
        if n_test < 0:
            n_val = n - n_train
            n_test = 0

        t = group[:n_train]
        v = group[n_train:n_train + n_val]
        te = group[n_train + n_val:]

        for e in t:
            e["metadata"]["split"] = "train"
        for e in v:
            e["metadata"]["split"] = "val"
        for e in te:
            e["metadata"]["split"] = "test"

        train_entries.extend(t)
        val_entries.extend(v)
        test_entries.extend(te)

    # Shuffle.
    random.shuffle(train_entries)
    random.shuffle(val_entries)
    random.shuffle(test_entries)

    all_final = train_entries + val_entries + test_entries

    def write_jsonl(entries: list[dict], path: Path) -> None:
        path.write_text(
            "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n",
            encoding="utf-8",
        )

    write_jsonl(all_final,      combined_dir / "full_dataset.jsonl")
    write_jsonl(train_entries,  combined_dir / "train.jsonl")
    write_jsonl(val_entries,    combined_dir / "val.jsonl")
    write_jsonl(test_entries,   combined_dir / "test.jsonl")

    counts = {
        "train": len(train_entries),
        "val": len(val_entries),
        "test": len(test_entries),
        "total": len(all_final),
    }

    print("Dataset split complete:")
    print(f"  train: {counts['train']}")
    print(f"  val  : {counts['val']}")
    print(f"  test : {counts['test']}")
    print(f"  total: {counts['total']}")

    return counts
