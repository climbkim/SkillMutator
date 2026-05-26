"""
evaluate_all.py - Run all evaluation steps for a single experiment in sequence.

Produce every CSV/figure required by the paper in one run.

Usage:
    # Evaluate the GPT-4o-mini dataset (default: result/ directory)
    python scripts/evaluate_all.py

    # Set a specific experiment directory
    python scripts/evaluate_all.py --result-dir experiments/gpt-4o-mini/result

    # Include the fine-tuned analysis (add base/ft paths)
    python scripts/evaluate_all.py \\
        --base-dir   result_260406 \\
        --finetune-dir eval_results_finetune/eval_results/mutations

    # also generate figures
    python scripts/evaluate_all.py --graph

Run order:
  1. baseline_analysis.py        -> baseline false-positive check  (Sec 2.3)
  2. merge_results.py            -> RQ1/RQ2/RQ4 scanner detection rate     (Sec 6.2-6.3, 6.6)
  3. analyze_select_ablation.py  -> Ablation A: select ON/OFF      (Sec 6.7)
  4. analyze_llm_detect_all_skills.py -> Ablation B: llm-detect   (Sec 6.7)
  5. analyze_finetuned.py        -> RQ3: base vs fine-tuned        (Sec 6.4)  [--base-dir required]
  6. analyze_multimodal.py       -> Multimodal vs MD-only injection-type analysis
"""

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR  = REPO_ROOT / "evaluation"


def run(cmd: list, label: str) -> bool:
    """Run a subprocess and return True on success."""
    print(f"\n{'='*60}")
    print(f"  [{label}]")
    print(f"  {' '.join(str(c) for c in cmd)}")
    print(f"{'='*60}")
    ret = subprocess.run(cmd, cwd=str(REPO_ROOT))
    ok  = ret.returncode == 0
    print(f"  -> {'OK' if ok else f'FAILED (exit {ret.returncode})'}")
    return ok


def main():
    parser = argparse.ArgumentParser(
        description="Run all evaluation steps in sequence",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/evaluate_all.py\n"
            "  python scripts/evaluate_all.py --result-dir experiments/gpt-4.1/result --graph\n"
            "  python scripts/evaluate_all.py --base-dir result_260406 "
            "--finetune-dir eval_results_finetune/eval_results/mutations\n"
        ),
    )
    parser.add_argument(
        "--result-dir", default="result",
        help="mutation results directory (default: result)"
    )
    parser.add_argument(
        "--out-dir", default=None,
        help="Evaluation output directory (default: {result-dir}/eval)"
    )
    parser.add_argument(
        "--base-dir", default=None,
        help="Base Qwen scan-results directory (for RQ3; skip Step 5 if absent)"
    )
    parser.add_argument(
        "--finetune-dir", default=None,
        help="Fine-tuned scan-results directory (for RQ3)"
    )
    parser.add_argument(
        "--graph", action="store_true",
        help="Generate figures (PNG/PDF)"
    )
    parser.add_argument(
        "--llm-scanner-model", default="",
        help="LLM-scanner model name (used in the figure legend, e.g. gpt-5.4-mini)"
    )
    parser.add_argument(
        "--skip-baseline", action="store_true",
        help="Skip Step 1 (baseline_analysis)"
    )
    parser.add_argument(
        "--skip-finetuned", action="store_true",
        help="Skip Step 5 (analyze_finetuned)"
    )
    parser.add_argument(
        "--skip-multimodal", action="store_true",
        help="Skip Step 6 (analyze_multimodal)"
    )
    parser.add_argument(
        "--multimodal-examples", type=int, default=10,
        help="Step 6: number of multimodal examples to print (default: 10)"
    )
    args = parser.parse_args()

    result_dir    = Path(args.result_dir).resolve()
    out_dir       = Path(args.out_dir).resolve() if args.out_dir else (result_dir / "eval")
    llm_scanner_model = args.llm_scanner_model

    print(f"\n{'#'*62}")
    print(f"  SkillMutator - Full Evaluation Pipeline")
    print(f"  result_dir : {result_dir}")
    print(f"  out_dir    : {out_dir}")
    print(f"{'#'*62}")

    results: dict[str, bool] = {}

    # -- Step 1: Baseline Analysis --
    if not args.skip_baseline:
        cmd = [sys.executable, str(EVAL_DIR / "baseline_analysis.py")]
        if not args.graph:
            cmd.append("--csv-only")
        results["Step 1: baseline_analysis"] = run(cmd, "Step 1 - Baseline Analysis (Sec 2.3)")
    else:
        print("\n[Step 1] Skipped (--skip-baseline)")

    # -- Step 2: merge_results --
    cmd = [
        sys.executable, str(EVAL_DIR / "merge_results.py"),
        "--result-dir", str(result_dir),
        "--out-dir",    str(out_dir / "merged"),
    ]
    if args.graph:
        cmd.append("--graph")
    if llm_scanner_model:
        cmd += ["--llm-scanner-model", llm_scanner_model]
    results["Step 2: merge_results"] = run(cmd, "Step 2 - Scanner Detection Rates (RQ1/RQ2/RQ4)")

    # -- Step 3: Select ablation --
    cmd = [
        sys.executable, str(EVAL_DIR / "analyze_select_ablation.py"),
        "--result-dir", str(result_dir),
    ]
    if args.graph:
        cmd.append("--graph")
    results["Step 3: select_ablation"] = run(cmd, "Step 3 - Ablation A: Select ON vs OFF (Sec 6.7)")

    # -- Step 4: LLM-detect ablation --
    cmd = [
        sys.executable, str(EVAL_DIR / "analyze_llm_detect_all_skills.py"),
        "--result-dir", str(result_dir),
    ]
    if args.graph:
        cmd.append("--graph")
    results["Step 4: llm_detect_ablation"] = run(cmd, "Step 4 - Ablation B: LLM-detect ON vs OFF (Sec 6.7)")

    # -- Step 5: Fine-tuned analysis (optional) --
    if not args.skip_finetuned:
        base_dir     = Path(args.base_dir).resolve()     if args.base_dir     else None
        finetune_dir = Path(args.finetune_dir).resolve() if args.finetune_dir else None

        if base_dir and finetune_dir:
            cmd = [
                sys.executable, str(EVAL_DIR / "analyze_finetuned.py"),
                "--base-dir",     str(base_dir),
                "--finetune-dir", str(finetune_dir),
                "--out-dir",      str(out_dir / "finetuned"),
                "--print",
            ]
            if args.graph:
                cmd.append("--graph")
            results["Step 5: analyze_finetuned"] = run(
                cmd, "Step 5 - RQ3: Base vs Fine-tuned Qwen (Sec 6.4)"
            )
        else:
            print("\n[Step 5] Skipped - --base-dir and --finetune-dir not provided")
            print("         Run: python scripts/generate_qwen_llm_report.py")
            print("              python scripts/generate_finetune_llm_report.py")
            print("         Then re-run with --base-dir and --finetune-dir")
    else:
        print("\n[Step 5] Skipped (--skip-finetuned)")

    # -- Step 6: Multimodal analysis --
    if not args.skip_multimodal:
        cmd = [
            sys.executable, str(EVAL_DIR / "analyze_multimodal.py"),
            "--result-dir", str(result_dir),
            "--out-dir",    str(out_dir / "multimodal"),
            "--examples",   str(args.multimodal_examples),
        ]
        if args.csv_only if hasattr(args, "csv_only") else False:
            cmd.append("--csv-only")
        results["Step 6: multimodal_analysis"] = run(
            cmd, "Step 6 - Multimodal vs MD-only Attack Breakdown"
        )
    else:
        print("\n[Step 6] Skipped (--skip-multimodal)")

    # -- Summary --
    print(f"\n{'#'*62}")
    print("  Evaluation Complete - Summary")
    print(f"{'#'*62}")
    for step, ok in results.items():
        status = "OK  " if ok else "FAIL"
        print(f"  {status}  {step}")
    print(f"\n  Output: {out_dir}")
    print(f"{'#'*62}")


if __name__ == "__main__":
    main()
