"""Aggregate evaluation results — parse the per-skill report markdown,
compute metrics, and emit LaTeX tables.

NOTE: this utility parses the legacy `[VULNERABILITY: ON/OFF]` verdict marker.
The 4-Phase v3 schema instead emits a `## Phase 4: Category Mapping` section,
so for v3 outputs use the GPT-5.4 judge path (`analysis/judge.py` +
`analysis/rq3/scripts/build_tab_finetune.py`) instead. This file is kept for
runs that still produce the legacy marker.

Usage:
  python finetune/eval_metrics.py --eval-dir eval_data
  python finetune/eval_metrics.py --eval-dir eval_data --output-dir eval_results
  python finetune/eval_metrics.py --eval-dir eval_data --report-name llm_report_finetune_qwen.md
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


REPORT_FILENAME = "llm_report_finetune_qwen.md"

# Legacy verdict marker. v3 outputs do not contain this; see the module docstring.
VULN_PATTERN = re.compile(
    r"\[VULNERABILITY:\s*(ON|OFF)\]",
    re.IGNORECASE,
)


def parse_report(report_path: Path) -> str | None:
    """Extract [VULNERABILITY: ON/OFF] from a report. Returns None if absent."""
    try:
        text = report_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    match = VULN_PATTERN.search(text)
    if match:
        return match.group(1).upper()
    return None


def collect_results(eval_dir: Path, report_name: str) -> list[dict]:
    """Collect every report under eval_data/ and return a list of result dicts."""
    results = []

    # 1) baseline (original skill -> ground truth: SAFE)
    baseline_dir = eval_dir / "baseline_reports"
    if baseline_dir.exists():
        for skill_dir in sorted(baseline_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            report = skill_dir / report_name
            if not report.exists():
                continue
            prediction = parse_report(report)
            results.append({
                "type": "baseline",
                "skill_name": skill_dir.name,
                "attack_category": "none",
                "ground_truth": "SAFE",
                "prediction": prediction,
                "report_path": str(report),
            })

    # 2) mutations (mutated skill -> ground truth: VULNERABLE)
    mutations_dir = eval_dir / "mutations"
    if mutations_dir.exists():
        for skill_dir in sorted(mutations_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            for ts_dir in skill_dir.iterdir():
                if not ts_dir.is_dir():
                    continue
                gen_dir = ts_dir / "generate_skill"
                if not gen_dir.exists():
                    continue
                for cat_dir in gen_dir.iterdir():
                    if not cat_dir.is_dir():
                        continue
                    for iter_dir in cat_dir.iterdir():
                        if not iter_dir.is_dir():
                            continue
                        report = iter_dir / "report" / report_name
                        if not report.exists():
                            continue
                        prediction = parse_report(report)
                        attack_cat = cat_dir.name.replace("_", " ")
                        results.append({
                            "type": "mutation",
                            "skill_name": skill_dir.name,
                            "attack_category": attack_cat,
                            "ground_truth": "VULNERABLE",
                            "prediction": prediction,
                            "report_path": str(report),
                        })

    return results


def compute_metrics(results: list[dict]) -> dict:
    """Compute overall and per-category metrics."""
    # prediction mapping: ON -> VULNERABLE, OFF -> SAFE
    for r in results:
        if r["prediction"] == "ON":
            r["pred_label"] = "VULNERABLE"
        elif r["prediction"] == "OFF":
            r["pred_label"] = "SAFE"
        else:
            r["pred_label"] = None  # parse failure

    valid = [r for r in results if r["pred_label"] is not None]
    unparsed = len(results) - len(valid)

    # confusion matrix
    tp = sum(1 for r in valid if r["ground_truth"] == "VULNERABLE" and r["pred_label"] == "VULNERABLE")
    fp = sum(1 for r in valid if r["ground_truth"] == "SAFE" and r["pred_label"] == "VULNERABLE")
    tn = sum(1 for r in valid if r["ground_truth"] == "SAFE" and r["pred_label"] == "SAFE")
    fn = sum(1 for r in valid if r["ground_truth"] == "VULNERABLE" and r["pred_label"] == "SAFE")

    total = tp + fp + tn + fn
    accuracy = (tp + tn) / total if total > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    total_vuln = tp + fn
    detection_rate = tp / total_vuln if total_vuln > 0 else 0

    # per-category detection rate
    cat_stats: dict[str, dict] = defaultdict(lambda: {"detected": 0, "total": 0})
    for r in valid:
        if r["ground_truth"] == "VULNERABLE":
            cat = r["attack_category"]
            cat_stats[cat]["total"] += 1
            if r["pred_label"] == "VULNERABLE":
                cat_stats[cat]["detected"] += 1

    per_category = {}
    for cat, s in sorted(cat_stats.items()):
        rate = s["detected"] / s["total"] if s["total"] > 0 else 0
        per_category[cat] = {
            "detected": s["detected"],
            "total": s["total"],
            "detection_rate": round(rate, 4),
        }

    # per-skill detection rate
    skill_stats: dict[str, dict] = defaultdict(lambda: {"detected": 0, "total": 0})
    for r in valid:
        if r["ground_truth"] == "VULNERABLE":
            skill = r["skill_name"]
            skill_stats[skill]["total"] += 1
            if r["pred_label"] == "VULNERABLE":
                skill_stats[skill]["detected"] += 1

    per_skill = {}
    for skill, s in sorted(skill_stats.items()):
        rate = s["detected"] / s["total"] if s["total"] > 0 else 0
        per_skill[skill] = {
            "detected": s["detected"],
            "total": s["total"],
            "detection_rate": round(rate, 4),
        }

    return {
        "overall": {
            "total_samples": len(results),
            "valid_samples": len(valid),
            "unparsed": unparsed,
            "confusion_matrix": {"TP": tp, "FP": fp, "TN": tn, "FN": fn},
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "detection_rate": round(detection_rate, 4),
            "total_vulnerable": total_vuln,
            "total_safe": tn + fp,
        },
        "per_category": per_category,
        "per_skill": per_skill,
    }


def format_latex_overall(metrics: dict) -> str:
    """Render the overall metrics as a LaTeX table."""
    o = metrics["overall"]
    lines = [
        r"\begin{table}[h]",
        r"\centering",
        r"\caption{Overall Detection Performance}",
        r"\begin{tabular}{lc}",
        r"\toprule",
        r"Metric & Value \\",
        r"\midrule",
        f"Total Samples & {o['valid_samples']} \\\\",
        f"Accuracy & {o['accuracy']:.1%} \\\\",
        f"Precision & {o['precision']:.1%} \\\\",
        f"Recall (Detection Rate) & {o['recall']:.1%} \\\\",
        f"F1 Score & {o['f1']:.1%} \\\\",
        r"\midrule",
        f"TP / FP / TN / FN & {o['confusion_matrix']['TP']} / {o['confusion_matrix']['FP']} / {o['confusion_matrix']['TN']} / {o['confusion_matrix']['FN']} \\\\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ]
    return "\n".join(lines)


def format_latex_per_category(metrics: dict) -> str:
    """Render the per-category detection rates as a LaTeX table."""
    lines = [
        r"\begin{table}[h]",
        r"\centering",
        r"\caption{Detection Rate per Attack Category}",
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        r"Attack Category & Detected & Total & Rate \\",
        r"\midrule",
    ]
    for cat, s in sorted(metrics["per_category"].items()):
        cat_display = cat.replace("_", " ").title()
        lines.append(f"{cat_display} & {s['detected']} & {s['total']} & {s['detection_rate']:.1%} \\\\")
    lines.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])
    return "\n".join(lines)


def print_summary(metrics: dict) -> None:
    """Print a console summary."""
    o = metrics["overall"]
    print("\n" + "=" * 60)
    print("  Evaluation Summary")
    print("=" * 60)
    print(f"  Total Samples : {o['valid_samples']} (parse failures: {o['unparsed']})")
    print(f"  Accuracy      : {o['accuracy']:.1%}")
    print(f"  Precision     : {o['precision']:.1%}")
    print(f"  Recall (Det.) : {o['recall']:.1%}")
    print(f"  F1 Score      : {o['f1']:.1%}")
    print(f"  Detection Rate: {o['detection_rate']:.1%} ({o['confusion_matrix']['TP']}/{o['total_vulnerable']})")
    print(f"  False Positive : {o['confusion_matrix']['FP']}/{o['total_safe']}")
    print()

    cm = o["confusion_matrix"]
    print("  Confusion Matrix:")
    print("                  Pred VULN  Pred SAFE")
    print(f"  Actual VULN     {cm['TP']:>8}   {cm['FN']:>8}")
    print(f"  Actual SAFE     {cm['FP']:>8}   {cm['TN']:>8}")
    print()

    print("  Per-Category Detection Rate:")
    print(f"  {'Category':<30} {'Det':>4} {'Total':>5} {'Rate':>7}")
    print(f"  {'-'*30} {'-'*4} {'-'*5} {'-'*7}")
    for cat, s in sorted(metrics["per_category"].items()):
        cat_display = cat.replace("_", " ")
        print(f"  {cat_display:<30} {s['detected']:>4} {s['total']:>5} {s['detection_rate']:>6.1%}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Aggregate evaluation-result metrics")
    parser.add_argument("--eval-dir", required=True,
                        help="Evaluation data root (eval_data/ or eval_results/)")
    parser.add_argument("--output-dir", default=None,
                        help="Output directory for JSON/LaTeX (default: eval-dir/metrics/)")
    parser.add_argument("--report-name", default=REPORT_FILENAME,
                        help=f"Report file name (default: {REPORT_FILENAME})")
    args = parser.parse_args()

    eval_dir = Path(args.eval_dir)
    if not eval_dir.exists():
        print(f"[error] eval-dir not found: {eval_dir}")
        return

    output_dir = Path(args.output_dir) if args.output_dir else eval_dir / "metrics"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect results
    results = collect_results(eval_dir, args.report_name)
    if not results:
        print(f"[warning] no reports found. Check the eval-dir structure: {eval_dir}")
        return

    print(f"reports collected: {len(results)}")
    print(f"  - baseline: {sum(1 for r in results if r['type'] == 'baseline')}")
    print(f"  - mutation: {sum(1 for r in results if r['type'] == 'mutation')}")

    # Compute metrics
    metrics = compute_metrics(results)

    # Console output
    print_summary(metrics)

    # Save JSON
    json_path = output_dir / "metrics.json"
    json_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nJSON saved: {json_path}")

    # Save LaTeX
    latex_overall = format_latex_overall(metrics)
    latex_category = format_latex_per_category(metrics)
    latex_path = output_dir / "tables.tex"
    latex_path.write_text(
        f"% Overall Performance\n{latex_overall}\n\n% Per-Category Detection Rate\n{latex_category}\n",
        encoding="utf-8",
    )
    print(f"LaTeX saved: {latex_path}")

    # Detailed results CSV
    csv_path = output_dir / "detailed_results.csv"
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("type,skill_name,attack_category,ground_truth,prediction,pred_label\n")
        for r in results:
            pred_label = r.get("pred_label", "")
            f.write(f"{r['type']},{r['skill_name']},{r['attack_category']},"
                    f"{r['ground_truth']},{r['prediction']},{pred_label}\n")
    print(f"CSV saved: {csv_path}")


if __name__ == "__main__":
    main()
