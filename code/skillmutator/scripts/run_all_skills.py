"""
run_all_skills.py — Run main.py sequentially or in parallel for all folders under skills/

Usage:
    python run_all_skills.py                          # run all skills (select ON, parallel)
    python run_all_skills.py pdf claude-api           # run specific skills only
    python run_all_skills.py -w 8                     # run with 8 parallel workers
    python run_all_skills.py --no-select              # ablation: all skills, select OFF
    python run_all_skills.py --no-select --use-llm-detect  # both options
"""

import argparse
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
import concurrent.futures

# Ensure UTF-8 output on the Windows console (reconfigure: encoding-only swap)
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

if sys.platform == "win64":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT  = Path(__file__).resolve().parent.parent   # skillmutator-github/
MAIN_PY    = REPO_ROOT / "skillmutator" / "main.py"
SKILLS_DIR = REPO_ROOT / "skills"


class _Tee:
    """Tee stdout/stderr to both the terminal and a file (thread-safe)."""
    def __init__(self, original, file_obj):
        self._original = original
        self._file = file_obj
        self._lock = threading.Lock()

    def write(self, data):
        with self._lock:
            self._original.write(data)
            self._file.write(data)

    def flush(self):
        self._original.flush()
        self._file.flush()

    def fileno(self):
        return self._original.fileno()


def run_skill_task(skill, index, total, args, mode_label):
    """Worker function that runs one skill."""
    cmd = [sys.executable, str(MAIN_PY), skill]
    if args.no_select:
        cmd.append("--no-select")
    if args.use_llm_detect:
        cmd.append("--use-llm-detect")
    if args.iterations != 3:
        cmd.extend(["--iterations", str(args.iterations)])
    if args.result_dir:
        cmd.extend(["--result-dir", args.result_dir])
    if args.model != "gpt-5.4-mini":
        cmd.extend(["--model", args.model])
    if args.provider != "openai":
        cmd.extend(["--provider", args.provider])
    if args.llm_mode != "direct":
        cmd.extend(["--llm-mode", args.llm_mode])

    # Capture output so parallel logs do not interleave
    import os
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    ret = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    return skill, index, total, ret


def main():
    parser = argparse.ArgumentParser(
        description="Batch skill mutation runner (Parallel Support)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python run_all_skills.py                              # all skills, select ON\n"
            "  python run_all_skills.py pdf docx                     # specific skills, select ON\n"
            "  python run_all_skills.py --no-select                  # all skills, select OFF (ablation)\n"
            "  python run_all_skills.py pdf --no-select              # specific skill, select OFF\n"
            "  python run_all_skills.py pdf --use-llm-detect         # include the LLM-scanner verdict in the regeneration trigger\n"
            "  python run_all_skills.py --no-select --use-llm-detect # use both options together\n"
            "  python run_all_skills.py -w 2                         # 2 parallel workers\n"
            "  python run_all_skills.py -n 5                         # max 5 times iteration\n"
            "  python run_all_skills.py -n 5 -w 3                    # 5 iterations, 3 parallel workers\n"
        ),
    )
    parser.add_argument(
        "skills",
        nargs="*",
        help="Folder name under skills/ (run all skills when unspecified)",
    )
    parser.add_argument(
        "--no-select",
        action="store_true",
        help="Skip node_select_attacks (ablation: all attack categories)",
    )
    parser.add_argument(
        "--use-llm-detect",
        action="store_true",
        help="Include the LLM-scanner verdict in the regeneration trigger (default: only ss/snyk)",
    )
    parser.add_argument(
        "-w", "--workers",
        type=int,
        default=1,
        help="Max parallel workers (default: 1, sequential)",
    )
    parser.add_argument(
        "--iterations", "-n",
        type=int,
        default=3,
        help="max iterations (default: 3, iter_0 ~ iter_{N-1})",
    )
    parser.add_argument(
        "--result-dir",
        default=None,
        dest="result_dir",
        help="results save directory (default: {repo}/result). "
             "Used to keep per-model experiments separate (e.g. experiments/gpt-4.1/result)",
    )
    parser.add_argument(
        "--model",
        default="gpt-5.4-mini",
        help="Mutation-generation LLM model name (default: gpt-5.4-mini)",
    )
    parser.add_argument(
        "--provider",
        default="openai",
        help="LLM provider (default: openai)",
    )
    parser.add_argument(
        "--llm-mode",
        default="direct",
        choices=["direct", "compare", "both"],
        dest="llm_mode",
        help="LLM detection style: 'direct' (default; judge the mutated scan MD directly), 'compare' (baseline vs mutated diff), or 'both' (run both; feedback uses 'direct')",
    )
    args = parser.parse_args()

    skills = args.skills if args.skills else sorted(
        p.name for p in SKILLS_DIR.iterdir() if p.is_dir()
    )
    total = len(skills)

    select_label = "select_OFF" if args.no_select else "select_ON"
    llm_label    = "+llm_detect" if args.use_llm_detect else ""
    iter_label   = f"_iter{args.iterations}" if args.iterations != 3 else ""
    mode_label   = select_label + llm_label + iter_label

    # ── results / log directory ─────────────────────────────────
    from pathlib import Path as _Path
    result_root = _Path(args.result_dir).resolve() if args.result_dir else (REPO_ROOT / "result")
    log_dir  = result_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"batch_{ts}_{mode_label}.log"

    log_file = open(log_path, "w", encoding="utf-8", buffering=1)
    sys.stdout = _Tee(sys.__stdout__, log_file)
    sys.stderr = _Tee(sys.__stderr__, log_file)

    print("=" * 52)
    print(f" Skill mutation batch run - {mode_label}")
    print(f" Model : {args.model}  Provider: {args.provider}")
    print(f" Skills: {total}  Workers: {args.workers}")
    print(f" Output: {result_root}")
    print(f" Log   : {log_path}")
    print("=" * 52)

    # Lock: protect the success/failed counters (avoid race conditions)
    result_lock = threading.Lock()
    print_lock  = threading.Lock()
    success = 0
    failed  = []

    # Pre-filter missing folders
    valid_skills = []
    for i, skill in enumerate(skills, 1):
        skill_path = SKILLS_DIR / skill
        if not skill_path.is_dir():
            print(f"\n[{i}/{total}] '{skill}' - folder not found in skills/, skipping")
            with result_lock:
                failed.append(skill)
        else:
            valid_skills.append((skill, i))

    # ── Parallel execution via ThreadPoolExecutor ─────────────────────────
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(run_skill_task, skill, i, total, args, mode_label): skill
            for skill, i in valid_skills
        }

        for future in concurrent.futures.as_completed(futures):
            skill, i, total_count, ret = future.result()

            with print_lock:
                print(f"\n{'─' * 52}")
                print(f"[{i}/{total_count}] Skill: {skill}  [{mode_label}]")
                print(f"{'─' * 52}")

                # print stdout/stderr captured from the subprocess
                if ret.stdout:
                    print(ret.stdout.strip())
                if ret.stderr:
                    print(ret.stderr.strip(), file=sys.stderr)

                with result_lock:
                    if ret.returncode == 0:
                        success += 1
                        print(f"[{i}/{total_count}] OK {skill} done")
                    else:
                        failed.append(skill)
                        print(f"[{i}/{total_count}] FAIL {skill} failed (exit {ret.returncode})")

    print(f"\n{'=' * 52}")
    print(f" Done: {success}/{total} succeeded  [{mode_label}]")
    if failed:
        print(f" Failed: {', '.join(failed)}")
    print(f" Log  : {log_path}")
    print("=" * 52)

    # Merge all per-skill CSVs into a single comparison_all.csv
    print(f"\n{'─' * 52}")
    print(" Merging CSVs...")
    print(f"{'─' * 52}")
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "evaluation" / "merge_csv.py"), "--summary"],
        cwd=str(REPO_ROOT),
    )

    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
    log_file.close()
    print(f"\n[batch] log saved: {log_path}")


if __name__ == "__main__":
    main()
