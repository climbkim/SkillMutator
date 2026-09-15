"""judge_scan_to_csv.py -- adjudicate one scan output into a judge_summary.csv row.

Bridges the demo scan step ([D] `infer.py` prints a scan to stdout) to the
table renderer ([F] `render_scan_tables.py`, which consumes a judge_summary.csv).
It runs the v2 judge (`analysis.judge.judge_call`) on a single scan against the
injected-attack ground truth and appends one row to a judge_summary.csv:

    skill,category,verdict          # verdict in {DETECTED, MISSED}

For the full benchmark you would instead judge every scenario in the scan tree
and aggregate (see analysis/judge.py + the rq3/rq4 builders); this helper is the
single-skill demo path.

Requires OPENAI_API_KEY (the judge is an OpenAI model; override with --judge-model).

Usage:
    python analysis/judge_scan_to_csv.py \\
        --scan-file    ${OUTPUT_DIR}/scan/scan.md \\
        --skill        markdown-link-checker \\
        --category     "Data Exfiltration" \\
        --injected-file experiments/sample/skill_mutated/SKILL.md \\
        --out-csv      ${OUTPUT_DIR}/scan/judge_summary.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Judge one scan output into a judge_summary.csv row.")
    ap.add_argument("--scan-file", required=True, help="Scanner output (markdown/text) to judge.")
    ap.add_argument("--skill", required=True, help="Skill name (for the CSV row / judge context).")
    ap.add_argument("--category", required=True, help="Injected attack category (ground truth).")
    ap.add_argument("--title", default="", help="Optional scenario title.")
    ap.add_argument("--injected-file", default=None,
                    help="File whose text is the injected-attack reference (e.g. mutated SKILL.md).")
    ap.add_argument("--out-csv", required=True, help="judge_summary.csv to write/append.")
    ap.add_argument("--judge-model", default=None, help="Override the judge model id.")
    args = ap.parse_args()

    # analysis/ is a top-level package at the framework root (judge.py + paths.py
    # + parsers.py); put the framework root on the path and import from there.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from analysis.judge import judge_call  # noqa: E402

    scan_text = Path(args.scan_file).read_text(encoding="utf-8")
    injected = (Path(args.injected_file).read_text(encoding="utf-8")
                if args.injected_file and Path(args.injected_file).is_file() else "")

    kw = {}
    if args.judge_model:
        kw["model"] = args.judge_model
    verdict = judge_call(skill=args.skill, category=args.category, title=args.title,
                         disguise="", injected_snippet=injected, scan_text=scan_text, **kw)

    detected = bool(verdict.get("detected"))
    label = "DETECTED" if detected else "MISSED"
    print(f"[judge] {args.skill} / {args.category}: {label} "
          f"(confidence={verdict.get('confidence')}) — {verdict.get('reason','')[:120]}")

    out = Path(args.out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    new = not out.is_file()
    with out.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["skill", "category", "verdict", "confidence"])
        w.writerow([args.skill, args.category, label, verdict.get("confidence", "")])
    print(f"[judge] wrote row -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
