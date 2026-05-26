"""
aggregate_test_scanner.py - aggregate-compare scanner experiments under test_scanner_result/.

Reads comparison_*.csv from each experiment directory under test_scanner_result/
and produces a table and a CSV comparing detection rates across scanner models.

Use --dataset to filter results to a single dataset.
Directory naming convention: {scanner}_scan_{dataset} (e.g. gpt-4o-mini_scan_gpt5.4_dataset)

Usage:
    python scripts/aggregate_test_scanner.py --dataset gpt5.4     # gpt-5.4 dataset only
    python scripts/aggregate_test_scanner.py --dataset gpt-4o-mini # gpt-4o-mini dataset only
    python scripts/aggregate_test_scanner.py                       # all experiments (not recommended; mixes datasets)
    python scripts/aggregate_test_scanner.py --experiments gpt-4o-mini_scan_gpt5.4_dataset gpt-5.4-mini_scan_gpt5.4_dataset
"""

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_experiment(exp_dir: Path) -> list[dict]:
    """Read every comparison_*.csv and return the rows as a list."""
    rows = []
    for csv_path in sorted(exp_dir.glob("comparison_*.csv")):
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                row = {k.strip().lstrip("\ufeff"): v for k, v in row.items()}
                rows.append(row)
    return rows


def _bool(val: str) -> bool:
    return str(val).strip().lower() == "true"


def compute_stats(rows: list[dict]) -> dict:
    """Compute overall, per-category, and per-skill detection rates."""
    total = len(rows)
    det_d = sum(1 for r in rows if _bool(r.get("llm_detected", "")))
    det_c = sum(1 for r in rows if _bool(r.get("llm_compare_detected", "")))
    has_compare = any(r.get("llm_compare_detected", "") != "" for r in rows)

    by_cat = defaultdict(lambda: {"n": 0, "direct": 0, "compare": 0})
    by_skill = defaultdict(lambda: {"n": 0, "direct": 0, "compare": 0})

    for r in rows:
        cat = r.get("attack_category", "unknown")
        sk = r.get("skill_name", "unknown")
        d = _bool(r.get("llm_detected", ""))
        c = _bool(r.get("llm_compare_detected", ""))

        by_cat[cat]["n"] += 1
        by_skill[sk]["n"] += 1
        if d:
            by_cat[cat]["direct"] += 1
            by_skill[sk]["direct"] += 1
        if c:
            by_cat[cat]["compare"] += 1
            by_skill[sk]["compare"] += 1

    return {
        "total": total,
        "det_direct": det_d,
        "det_compare": det_c,
        "has_compare": has_compare,
        "rate_direct": det_d / total if total else 0,
        "rate_compare": det_c / total if total else 0,
        "by_cat": dict(by_cat),
        "by_skill": dict(by_skill),
    }


def print_overall(all_stats: dict[str, dict]) -> list[dict]:
    """Print the overall detection-rate table and return CSV rows."""
    print(f"\n{'='*70}")
    print(f"  Overall Detection Rate")
    print(f"{'='*70}")
    print(f"  {'Experiment':<45} {'N':>4} {'Direct':>10} {'Compare':>10}")
    print(f"  {'-'*70}")

    csv_rows = []
    for name, st in all_stats.items():
        dr = f"{st['rate_direct']*100:.1f}%"
        cr = f"{st['rate_compare']*100:.1f}%" if st["has_compare"] else "N/A"
        print(f"  {name:<45} {st['total']:>4} {dr:>10} {cr:>10}")
        csv_rows.append({
            "experiment": name,
            "n": st["total"],
            "direct_detected": st["det_direct"],
            "direct_rate": round(st["rate_direct"], 4),
            "compare_detected": st["det_compare"],
            "compare_rate": round(st["rate_compare"], 4) if st["has_compare"] else "",
        })
    return csv_rows


def print_by_dimension(all_stats: dict[str, dict], dim: str, label: str) -> list[dict]:
    """Print a per-category or per-skill comparison table."""
    all_keys = set()
    for st in all_stats.values():
        all_keys |= set(st[dim].keys())

    experiments = list(all_stats.keys())
    short_names = [e.split("_scan_")[0] if "_scan_" in e else e[:20] for e in experiments]

    print(f"\n{'='*70}")
    print(f"  By {label} (Direct mode)")
    print(f"{'='*70}")

    header = f"  {label:<30}"
    for sn in short_names:
        header += f" {sn:>12}"
    print(header)
    print(f"  {'-'*70}")

    csv_rows = []
    for key in sorted(all_keys):
        line = f"  {key:<30}"
        row = {label.lower(): key}
        for exp_name, sn in zip(experiments, short_names):
            d = all_stats[exp_name][dim].get(key, {"n": 0, "direct": 0})
            if d["n"] > 0:
                rate = d["direct"] / d["n"] * 100
                line += f" {rate:>7.1f}%({d['n']:>2})"
                row[f"{sn}_rate"] = round(d["direct"] / d["n"], 4)
                row[f"{sn}_n"] = d["n"]
            else:
                line += f" {'N/A':>12}"
        print(line)
        csv_rows.append(row)
    return csv_rows


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    # Collect the union of every row's keys
    all_keys = []
    seen = set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                all_keys.append(k)
                seen.add(k)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="test_scanner_result aggregate comparison")
    parser.add_argument("--result-root", default="test_scanner_result",
                        help="test_scanner_result root (default: test_scanner_result/)")
    parser.add_argument("--dataset", default=None,
                        help="Filter to a specific dataset (substring of the directory name, e.g. gpt5.4, gpt-4o-mini)")
    parser.add_argument("--experiments", nargs="*", default=None,
                        help="Specify experiment directory names directly (takes precedence over --dataset)")
    parser.add_argument("--out-dir", default=None,
                        help="CSV save directory (default: {result-root}/aggregate_{dataset}/)")
    args = parser.parse_args()

    result_root = Path(args.result_root).resolve()
    if not result_root.is_dir():
        print(f"[error] {result_root} not found")
        sys.exit(1)

    # Enumerate experiment directories
    if args.experiments:
        exp_dirs = [result_root / e for e in args.experiments]
    else:
        exp_dirs = sorted(
            p for p in result_root.iterdir()
            if p.is_dir()
            and not p.name.startswith("aggregate")
            and list(p.glob("comparison_*.csv"))
        )
        # apply --dataset filter
        if args.dataset:
            exp_dirs = [p for p in exp_dirs if args.dataset in p.name]

    if not exp_dirs:
        filt_msg = f" (filter: '{args.dataset}')" if args.dataset else ""
        print(f"[error] No experiments found in {result_root}{filt_msg}")
        sys.exit(1)

    # Extract dataset label (used in output directory and table header)
    dataset_label = args.dataset or "all"
    out_dir = (
        Path(args.out_dir).resolve()
        if args.out_dir
        else result_root / f"aggregate_{dataset_label}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*70}")
    print(f"  Aggregate Test Scanner Results")
    print(f"  Dataset filter : {dataset_label}")
    print(f"  Experiments    : {len(exp_dirs)}")
    print(f"  Output         : {out_dir}")
    print(f"{'='*70}")

    # Load data
    all_stats: dict[str, dict] = {}
    for exp_dir in exp_dirs:
        if not exp_dir.is_dir():
            print(f"  [warn] {exp_dir.name} not found, skipping")
            continue
        rows = load_experiment(exp_dir)
        if not rows:
            print(f"  [warn] {exp_dir.name}: no data")
            continue
        all_stats[exp_dir.name] = compute_stats(rows)
        print(f"  [loaded] {exp_dir.name}: {len(rows)} rows")

    # output
    overall_rows = print_overall(all_stats)
    cat_rows = print_by_dimension(all_stats, "by_cat", "Category")
    skill_rows = print_by_dimension(all_stats, "by_skill", "Skill")

    # CSV save
    write_csv(out_dir / "overall.csv", overall_rows)
    write_csv(out_dir / "by_category.csv", cat_rows)
    write_csv(out_dir / "by_skill.csv", skill_rows)

    print(f"\n{'='*70}")
    print(f"  CSV saved -> {out_dir}")
    print(f"  Dataset   : {dataset_label}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
