"""
run_test_scanner.py — Post-hoc LLM scanner runner on existing mutation results.

Architecture
------------
- Scanner model (e.g. Qwen): runs scan.py --scanner llm on existing mutated skills
- Mutation: unchanged (reads from existing result/ data)
- Judgment: main GPT model calls _compare_llm_direct() or _compare_llm()

Output directory (fully separate from main results):
  {out_dir}/
    comparison_{skill}.csv
    {skill}/{run_id}/generate_skill/{cat}/iter_N/
        logs/llm-scanner/    ← scanner (Qwen) outputs
        report/llm_report.md ← judgment by GPT

  For compare mode, Qwen baseline scan is also saved under:
  {out_dir}/baseline/{skill}/llm-scanner/

Usage
-----
    python scripts/run_test_scanner.py                              # all skills, direct mode
    python scripts/run_test_scanner.py pdf docx                     # specific skills
    python scripts/run_test_scanner.py \\
        --scanner-provider qwen --scanner-model Qwen/Qwen2.5-7B-Instruct \\
        --judge-provider openai --judge-model gpt-4.1-mini \\
        --llm-mode direct
    python scripts/run_test_scanner.py --llm-mode compare           # baseline vs mutated
    python scripts/run_test_scanner.py --result-dir experiments/gpt-4.1/result
"""

import argparse
import csv as csv_module
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
import sys as _sys
_SRC = REPO_ROOT / "src"
if str(_SRC) not in _sys.path:
    _sys.path.insert(0, str(_SRC))
SCAN_PY   = REPO_ROOT / "skillmutator" / "scan.py"

# Add the skillmutator package path
sys.path.insert(0, str(REPO_ROOT / "skillmutator"))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / ".env")

# Windows console UTF-8
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ─────────────────────────────────────────────────────────────────────
# Metadata loaders
# ─────────────────────────────────────────────────────────────────────

def _load_latest_json(directory: Path):
    """Return parsed content of the most recently modified .json file in directory."""
    if not directory or not directory.exists():
        return None
    files = list(directory.glob("*.json"))
    if not files:
        return None
    f = max(files, key=lambda p: p.stat().st_mtime)
    return json.loads(f.read_text(encoding="utf-8"))


def load_run_metadata(base_dir: Path) -> dict:
    """Reconstruct a partial result dict from the saved JSON node outputs.

    Loads:
      attack_scenarios  ← base_dir/generate_scenarios/*.json
      selected_attacks  ← base_dir/select_attacks/*.json  (or select_attacks_bypass/)
    """
    # attack_scenarios
    attack_scenarios = _load_latest_json(base_dir / "generate_scenarios") or []
    if isinstance(attack_scenarios, dict):
        attack_scenarios = attack_scenarios.get("attack_scenarios", [])

    # selected_attacks — stored as selection_result["selected"]
    for sel_dir_name in ("select_attacks", "select_attacks_bypass"):
        sel_dir = base_dir / sel_dir_name
        if sel_dir.exists():
            selection_result = _load_latest_json(sel_dir)
            break
    else:
        selection_result = None

    if isinstance(selection_result, dict):
        selected_attacks = selection_result.get("selected", [])
    elif isinstance(selection_result, list):
        selected_attacks = selection_result
    else:
        selected_attacks = []

    # timestamp: base_dir.name = "{YYYYMMDD}_{HHMMSS}_{mode}"
    parts = base_dir.name.split("_")
    timestamp = "_".join(parts[:2]) if len(parts) >= 2 else base_dir.name

    return {
        "attack_scenarios": attack_scenarios,
        "selected_attacks": selected_attacks,
        "timestamp":        timestamp,
    }


def load_generated_skills(base_dir: Path, iteration: int) -> list:
    """Load generated_skills list for a specific iteration from disk."""
    data = _load_latest_json(base_dir / f"generate_skill_iter{iteration}")
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("generated_skills", [])
    return []


# ─────────────────────────────────────────────────────────────────────
# Scanner runner
# ─────────────────────────────────────────────────────────────────────

SCANNER_PY = REPO_ROOT / "scanners" / "llm-scanner" / "scanner.py"


def run_llm_scanner(
    skills_path: Path,
    log_dir: Path,
    scanner_provider: str,
    scanner_model: str,
    base_url: str | None = None,
    max_tokens: int | None = None,
) -> int:
    """Run scanner.py directly on skills_path, save logs to log_dir.

    When base_url is set, call scanner.py directly (preferred over the scan.py wrapper).
    Without base_url, use the existing scan.py wrapper.
    """
    if base_url:
        # Direct scanner.py call (GPU server or other custom endpoint)
        cmd = [
            sys.executable,
            str(SCANNER_PY),
            "-p", scanner_provider,
            "-s", str(skills_path.resolve()),
            "-o", str(log_dir),
        ]
        if scanner_model:
            cmd.extend(["-m", scanner_model])
        cmd.extend(["-u", base_url])
        if max_tokens:
            cmd.extend(["-t", str(max_tokens)])
    else:
        # Call via the existing scan.py wrapper
        cmd = [
            sys.executable,
            str(SCAN_PY),
            str(skills_path.resolve()),
            "--scanner", "llm",
            f"--log-dir={log_dir}",
            "--provider", scanner_provider,
        ]
        if scanner_model:
            cmd.extend(["--model", scanner_model])

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    ret = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env)
    return ret.returncode


# ─────────────────────────────────────────────────────────────────────
# Core processor
# ─────────────────────────────────────────────────────────────────────

def process_run(
    base_dir: Path,
    skill_name: str,
    test_out_dir: Path,
    csv_path: Path,
    scanner_provider: str,
    scanner_model: str,
    judge_llm,
    llm_mode: str,
    scanner_base_url: str | None = None,
    scanner_max_tokens: int | None = None,
    skip_scan: bool = False,
    judge_provider: str = "",
    judge_model: str = "",
) -> None:
    """Run test scanner + judgment for all iters in one run_id directory.

    Args:
        base_dir:         existing {result_dir}/{skill}/{run_id}/
        skill_name:       e.g. "pdf"
        test_out_dir:     root of test scanner output (separate from result/)
        csv_path:         CSV file to append rows to
        scanner_provider: e.g. "qwen"
        scanner_model:    e.g. "Qwen/Qwen2.5-7B-Instruct"
        judge_llm:        LLM instance for judgment (GPT or any main model)
        llm_mode:         "direct" | "compare"
    """
    from skill_mutator.process.compare import (
        _compare_llm_direct,
        _compare_llm,
        generate_llm_report,
        find_latest_file,
    )
    from skill_mutator.process.skill_mutation import _to_safe_dirname

    meta             = load_run_metadata(base_dir)
    attack_scenarios = meta["attack_scenarios"]
    selected_attacks = meta["selected_attacks"]
    timestamp_str    = meta["timestamp"]

    if not attack_scenarios:
        print(f"  [skip] No attack_scenarios found under {base_dir}")
        return

    # Index selected_attacks by category
    sel_index: dict[str, dict] = {}
    for sa in selected_attacks:
        cat = _to_safe_dirname(sa.get("attack_category", ""))
        sel_index[cat] = sa

    # ── compare/both mode: ensure baseline scan exists ───────────────
    test_baseline_llm_dir = test_out_dir / "baseline" / skill_name / "llm-scanner"
    if llm_mode in ("compare", "both"):
        bl_qwen_md = find_latest_file(test_baseline_llm_dir, "*.md")
        if bl_qwen_md is None:
            skill_original = REPO_ROOT / "skills" / skill_name
            if skill_original.exists():
                print(f"  [baseline] Running baseline scan for '{skill_name}'...")
                run_llm_scanner(
                    skill_original,
                    test_out_dir / "baseline" / skill_name,
                    scanner_provider,
                    scanner_model,
                    base_url=scanner_base_url,
                    max_tokens=scanner_max_tokens,
                )
            else:
                print(f"  [baseline] WARNING: original skill not found at {skill_original}")

    # ── iterate over iterations ──────────────────────────────────────
    rows = []
    gen_skill_root = base_dir / "generate_skill"

    for iteration in range(20):  # max 20 iter search
        generated_skills = load_generated_skills(base_dir, iteration)

        # iteration 0: if generated_skills is missing (e.g. no file), check the actual skills folder
        # iteration > 0: if generated_skills is missing, there are no more iters
        if not generated_skills and iteration > 0:
            break

        gen_index: dict[str, dict] = {}
        for gs in generated_skills:
            if gs.get("parse_error"):
                continue
            cat = _to_safe_dirname(gs.get("attack_category", ""))
            gen_index[cat] = gs

        iter_label = f"iter_{iteration}"

        # Check whether the iter has at least one skills folder
        any_skills = any(
            (gen_skill_root / _to_safe_dirname(s.get("attack_category", "")) / iter_label / "skills").exists()
            for s in attack_scenarios if not s.get("parse_error")
        )
        if not any_skills:
            if iteration == 0:
                print(f"  [iter_0] No skills directories found under {gen_skill_root}")
            break

        for scenario in attack_scenarios:
            if scenario.get("parse_error"):
                continue

            attack_cat = scenario.get("attack_category", "unknown")
            safe_cat   = _to_safe_dirname(attack_cat)

            skills_path = gen_skill_root / safe_cat / iter_label / "skills"
            if not skills_path.exists():
                print(f"  [{iter_label}] {attack_cat}: skills not found, skipping")
                continue

            sel = sel_index.get(safe_cat, {})

            # ── test output dir for this run/category/iter ──────────
            test_iter_dir = (
                test_out_dir / skill_name / base_dir.name
                / "generate_skill" / safe_cat / iter_label
            )
            test_log_dir = test_iter_dir / "logs"

            # ── run scanner (Qwen) ───────────────────────────────────
            if not skip_scan:
                print(f"  [{iter_label}] {attack_cat}: scanning...")
                run_llm_scanner(skills_path, test_log_dir, scanner_provider, scanner_model, base_url=scanner_base_url, max_tokens=scanner_max_tokens)
            else:
                print(f"  [{iter_label}] {attack_cat}: scan skipped, judging...")

            # ── judgment (GPT) ───────────────────────────────────────
            mut_qwen_md = find_latest_file(test_log_dir / "llm-scanner", "*.md")
            if mut_qwen_md is None:
                mut_qwen_md = find_latest_file(test_log_dir, "*.md")
            if mut_qwen_md is None:
                print(f"  [{iter_label}] {attack_cat}: scan result MD not found, skipping judge")
                continue

            llm_compare_detected: bool = False
            llm_compare_reason:   str  = ""

            _sc_title = scenario.get("scenario_title", "")
            _sc_behav = scenario.get("actual_behavior", "")
            _sc_disg  = sel.get("disguise_as", "")

            if llm_mode == "direct":
                llm_detected, bl_findings, mut_findings, llm_reason = _compare_llm_direct(
                    mut_qwen_md, attack_cat, _sc_title, _sc_behav, _sc_disg, judge_llm,
                )
            elif llm_mode == "compare":
                bl_qwen_md = find_latest_file(test_baseline_llm_dir, "*.md")
                llm_detected, bl_findings, mut_findings, llm_reason = _compare_llm(
                    bl_qwen_md, mut_qwen_md,
                    attack_cat, _sc_title, _sc_behav, _sc_disg, judge_llm,
                )
            else:  # both
                # direct → llm_detected (primary)
                llm_detected, bl_findings, mut_findings, llm_reason = _compare_llm_direct(
                    mut_qwen_md, attack_cat, _sc_title, _sc_behav, _sc_disg, judge_llm,
                )
                # compare → llm_compare_detected (secondary)
                bl_qwen_md = find_latest_file(test_baseline_llm_dir, "*.md")
                llm_compare_detected, _, _, llm_compare_reason = _compare_llm(
                    bl_qwen_md, mut_qwen_md,
                    attack_cat, _sc_title, _sc_behav, _sc_disg, judge_llm,
                )

            status = "detected" if llm_detected else "not detected"
            extra = f", compare={llm_compare_detected}" if llm_mode == "both" else ""
            print(f"  [{iter_label}] {attack_cat}: {status} (mode={llm_mode}{extra})")

            # ── save report ──────────────────────────────────────────
            report_dir = test_iter_dir / "report"
            generate_llm_report(
                baseline_md=find_latest_file(test_baseline_llm_dir, "*.md") if llm_mode in ("compare", "both") else None,
                mutated_md=mut_qwen_md,
                scenario=scenario,
                sel=sel,
                llm_detected=llm_detected,
                llm_reason=llm_reason,
                skills_path=skills_path,
                llm=judge_llm,
                report_dir=report_dir,
            )
            if llm_mode == "both":
                generate_llm_report(
                    baseline_md=find_latest_file(test_baseline_llm_dir, "*.md"),
                    mutated_md=mut_qwen_md,
                    scenario=scenario,
                    sel=sel,
                    llm_detected=llm_compare_detected,
                    llm_reason=llm_compare_reason,
                    skills_path=skills_path,
                    llm=judge_llm,
                    report_dir=report_dir,
                    report_name="llm_compare_report.md",
                )

            row = {
                "skill_name":            skill_name,
                "run_id":                base_dir.name,
                "mutation_timestamp":    timestamp_str,
                "mutation_iteration":    iteration,
                "attack_category":       attack_cat,
                "scenario_title":        scenario.get("scenario_title", ""),
                "detection_difficulty":  scenario.get("detection_difficulty", ""),
                "disguise_as":           sel.get("disguise_as", ""),
                "entry_point":           sel.get("entry_point", ""),
                "scanner_provider":      scanner_provider,
                "scanner_model":         scanner_model,
                "judge_provider":        judge_provider,
                "judge_model":           judge_model,
                "llm_mode":              llm_mode,
                "llm_detected":          llm_detected,
                "llm_detection_reason":  llm_reason,
                "llm_baseline_findings": bl_findings,
                "llm_mutated_findings":  mut_findings,
                "actual_behavior":       scenario.get("actual_behavior", ""),
            }
            if llm_mode == "both":
                row["llm_compare_detected"]  = llm_compare_detected
                row["llm_compare_reason"]    = llm_compare_reason
            rows.append(row)

    if not rows:
        print(f"  [skip] No rows generated for {base_dir.name}")
        return

    # ── write CSV ────────────────────────────────────────────────────
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not csv_path.exists()
    fieldnames   = list(rows[0].keys())

    with open(csv_path, "a", encoding="utf-8", newline="") as f:
        writer = csv_module.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)

    print(f"  [csv] {len(rows)} rows written → {csv_path}")


# ─────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Post-hoc LLM scanner runner on existing mutation results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/run_test_scanner.py\n"
            "  python scripts/run_test_scanner.py pdf docx\n"
            "  python scripts/run_test_scanner.py \\\n"
            "      --scanner-provider qwen --scanner-model Qwen/Qwen2.5-7B-Instruct \\\n"
            "      --judge-provider openai --judge-model gpt-4.1-mini\n"
            "  python scripts/run_test_scanner.py --llm-mode compare\n"
            "  python scripts/run_test_scanner.py --result-dir experiments/gpt-4.1/result\n"
        ),
    )
    parser.add_argument(
        "skills", nargs="*",
        help="skills/ folder names to process (default: all found in result-dir)",
    )
    parser.add_argument(
        "--result-dir", default="result",
        help="existing mutation result root (default: result/)",
    )
    parser.add_argument(
        "--out-dir", default=None,
        help="test scanner output root (default: test_scanner_result/{scanner_label}/)",
    )
    parser.add_argument(
        "--scanner-provider", default="openai",
        help="LLM scanner provider, e.g. 'qwen' (default: openai)",
    )
    parser.add_argument(
        "--scanner-model", default="",
        help="LLM scanner model, e.g. 'Qwen/Qwen2.5-7B-Instruct'",
    )
    parser.add_argument(
        "--judge-provider", default="openai",
        help="Judgment model provider (default: openai)",
    )
    parser.add_argument(
        "--judge-model", default="gpt-4.1-mini",
        help="Judgment model name (default: gpt-4.1-mini)",
    )
    parser.add_argument(
        "--llm-mode", default="direct", choices=["direct", "compare", "both"],
        help="Judgment mode: direct (default) | compare (scan vs baseline) | both (direct + compare)",
    )
    parser.add_argument(
        "--scanner-base-url", default=None,
        help="Custom OpenAI-compatible endpoint for the scanner (e.g. http://host:8000/v1)",
    )
    parser.add_argument(
        "--scanner-max-tokens", type=int, default=None,
        help="Scanner input-token cap (recommended for Qwen-7B: 20000)",
    )
    parser.add_argument(
        "--skip-scan", action="store_true",
        help="Skip scanning; re-run only the judge against existing logs",
    )
    parser.add_argument(
        "--run-filter", default=None,
        help="run_id substring filter (e.g. 'no-select' -> only *_no-select* directories)",
    )
    args = parser.parse_args()

    from skill_mutator.llm import create_llm

    result_root = Path(args.result_dir).resolve()

    # scanner_label: used as subdirectory name under test_scanner_result/
    scanner_label = (
        f"{args.scanner_provider}_{args.scanner_model.replace('/', '-')}"
        if args.scanner_model
        else args.scanner_provider
    )
    test_out_dir = (
        Path(args.out_dir).resolve()
        if args.out_dir
        else (REPO_ROOT / "test_scanner_result" / scanner_label)
    )

    # determine skills to process
    if args.skills:
        skills = args.skills
    elif result_root.exists():
        skills = sorted(p.name for p in result_root.iterdir() if p.is_dir())
    else:
        skills = []

    if not skills:
        print(f"[test-scanner] No skills found in {result_root}")
        return

    print("=" * 60)
    print(f" Test Scanner Run")
    print(f" Scanner : {args.scanner_provider} / {args.scanner_model or '(default)'}")
    if args.scanner_base_url:
        print(f" Base URL: {args.scanner_base_url}")
    print(f" Judge   : {args.judge_provider} / {args.judge_model}")
    print(f" Mode    : {args.llm_mode}")
    if args.skip_scan:
        print(f" Skip    : scan skipped (judge-only re-run)")
    if args.run_filter:
        print(f" Filter  : run_id contains '{args.run_filter}'")
    print(f" Source  : {result_root}")
    print(f" Output  : {test_out_dir}")
    print(f" Skills  : {skills}")
    print("=" * 60)

    judge_llm = create_llm(provider=args.judge_provider, model_name=args.judge_model)

    for skill_name in skills:
        skill_result_dir = result_root / skill_name
        if not skill_result_dir.exists():
            print(f"\n[{skill_name}] not found in {result_root}, skipping")
            continue

        # find valid run dirs: must have generate_scenarios/ subfolder
        run_dirs = sorted(
            p for p in skill_result_dir.iterdir()
            if p.is_dir() and (p / "generate_scenarios").exists()
        )
        if args.run_filter:
            run_dirs = [p for p in run_dirs if args.run_filter in p.name]
        if not run_dirs:
            filter_msg = f" matching '{args.run_filter}'" if args.run_filter else ""
            print(f"\n[{skill_name}] no valid run dirs found{filter_msg} in {skill_result_dir}")
            continue

        csv_path = test_out_dir / f"comparison_{skill_name}.csv"
        print(f"\n[{skill_name}] {len(run_dirs)} run(s) found")

        for run_dir in run_dirs:
            print(f"\n── {skill_name}/{run_dir.name}")
            process_run(
                base_dir=run_dir,
                skill_name=skill_name,
                test_out_dir=test_out_dir,
                csv_path=csv_path,
                scanner_provider=args.scanner_provider,
                scanner_model=args.scanner_model,
                judge_llm=judge_llm,
                llm_mode=args.llm_mode,
                scanner_base_url=args.scanner_base_url,
                scanner_max_tokens=args.scanner_max_tokens,
                skip_scan=args.skip_scan,
                judge_provider=args.judge_provider,
                judge_model=args.judge_model,
            )

    print(f"\n{'=' * 60}")
    print(f" Done. Results in {test_out_dir}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
