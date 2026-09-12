"""SkillMutator command-line entry point and end-to-end example flow.

`example_skill_mutation()` is the canonical mutate -> scan -> compare ->
refine loop that drives the SkillMutator pipeline for one skill. The
`__main__` block exposes it as a CLI.

For batch sweeps across many skills, see `scripts/run_all_skills.py`.
"""

import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root (OPENAI_API_KEY, HF_TOKEN, ...).
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_REPO_ROOT / ".env")

from .llm import create_llm, build_chain, build_graph  # noqa: E402
from .process import Pipeline, run_skill_mutation, build_comparison_csv  # noqa: E402
from .process.refine_mutation import refine_skill_mutation, _is_detected  # noqa: E402


# ----------------------------------------------------------------------
# Logging helpers
# ----------------------------------------------------------------------

class _Tee:
    """Mirror stdout/stderr to both the terminal and a log file."""
    def __init__(self, original, file_obj):
        self._original = original
        self._file = file_obj

    def write(self, data):
        self._original.write(data)
        self._file.write(data)

    def flush(self):
        self._original.flush()
        self._file.flush()

    def fileno(self):          # for subprocess and other callers that need fileno()
        return self._original.fileno()


def _start_run_log(log_path: Path):
    """Install a tee at `log_path` and return the underlying file object."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    f = open(log_path, "w", encoding="utf-8", buffering=1)
    sys.stdout = _Tee(sys.__stdout__, f)
    sys.stderr = _Tee(sys.__stderr__, f)
    return f


def _stop_run_log(f):
    """Detach the tee and close the log file."""
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
    f.close()


# ----------------------------------------------------------------------
# Example 1: simple LLM call
# ----------------------------------------------------------------------
def example_basic_call():
    llm = create_llm("openai", model_name="gpt-4o-mini")
    response = llm.call("Explain in one sentence what a decorator is in Python.")
    print("[basic call]", response)


# ----------------------------------------------------------------------
# Example 2: chat-style call
# ----------------------------------------------------------------------
def example_chat():
    llm = create_llm("openai", model_name="gpt-4o-mini")
    messages = [
        {"role": "system", "content": "You are a Python expert."},
        {"role": "user", "content": "Briefly explain list comprehensions."},
    ]
    response = llm.chat(messages)
    print("[chat call]", response)


# ----------------------------------------------------------------------
# Example 3: read a folder and hand it to the LLM
# ----------------------------------------------------------------------
def example_folder_analysis():
    pipeline = Pipeline(provider="openai", model_name="gpt-4o-mini")
    result = pipeline.analyze_folder(
        folder_path=".",
        instruction="Describe the structure of this project and the role of each file.",
        extensions=[".py"],
    )
    print("[folder analysis]\n", result)


# ----------------------------------------------------------------------
# Example 4: LangChain chain
# ----------------------------------------------------------------------
def example_chain():
    llm = create_llm("openai", model_name="gpt-4o-mini")
    chain = build_chain(
        llm,
        prompt_template="Translate the following text into {language}:\n\n{text}",
    )
    result = chain.invoke({"language": "French", "text": "Hello, nice to meet you."})
    print("[LangChain]", result)


# ----------------------------------------------------------------------
# Example 5: LangGraph
# ----------------------------------------------------------------------
def example_graph():
    from typing import TypedDict

    class State(TypedDict):
        input: str
        summary: str
        keywords: str

    llm = create_llm("openai", model_name="gpt-4o-mini")

    def summarize(state: State) -> State:
        result = llm.call(f"Summarize in one sentence: {state['input']}")
        return {"summary": result}

    def extract_keywords(state: State) -> State:
        result = llm.call(f"Extract three keywords from: {state['summary']}")
        return {"keywords": result}

    graph = build_graph(
        llm,
        nodes={"summarize": summarize, "extract_keywords": extract_keywords},
        edges=[("summarize", "extract_keywords"), ("extract_keywords", "END")],
        entry_point="summarize",
        state_schema=State,
    )

    output = graph.invoke({"input": "Artificial intelligence is the technology of mimicking human intelligence."})
    print("[LangGraph]", output)


# ----------------------------------------------------------------------
# Helper: list attack categories that were detected for an iteration.
# ----------------------------------------------------------------------
def _get_detected_categories(result: dict, iter_label: str, use_llm_scanner: bool = False) -> list[str]:
    """Return the list of attack-category names detected at the given iteration.

    Args:
        use_llm_scanner: if True, the LLM-scanner verdict is included in the
            refinement-trigger logic; otherwise only ss/snyk results count.
    """
    detected = []
    for p in result.get("saved_paths", []):
        sp = Path(p)
        if not (sp.is_dir() and sp.name == "skills" and sp.parent.name == iter_label):
            continue
        iter_dir = sp.parent  # iter_{N}/
        if _is_detected(iter_dir, use_llm_scanner=use_llm_scanner):
            category = sp.parent.parent.name
            detected.append(category)
    return detected


# ----------------------------------------------------------------------
# Example 6: iterative skill mutation (the SkillMutator main flow)
# ----------------------------------------------------------------------
def example_skill_mutation(skill_name: str = "pdf", use_select_attacks: bool = True,
                           use_llm_detect: bool = False, max_iterations: int = 3,
                           result_root: str = None, model_name: str = "gpt-5.4-mini",
                           provider: str = "openai", llm_mode: str = "direct"):
    """Mutate, scan, and (when detected) regenerate a skill across iterations.

    Args:
        use_select_attacks: True (default) -> run the full 5-stage flow that
                            includes the `node_select_attacks` step.
                            False          -> skip the selection step (ablation:
                                              all attack categories are emitted).
        use_llm_detect:     True           -> include the LLM-scanner verdict in
                                              the refinement trigger.
                            False (default) -> use only ss/snyk verdicts.
        max_iterations:     maximum number of iterations (default: 3, iter_0 .. iter_{N-1}).
        result_root:        top-level output directory (default: {repo}/result).
        model_name:         LLM model used to generate the mutation (default: gpt-5.4-mini).
        provider:           LLM provider (default: openai).
        llm_mode:           LLM-based detection style.
                            "direct"  (default): the LLM is shown the injected content,
                                                 the scenario, and the skill files, and
                                                 makes the call directly.
                            "compare":           compare baseline and mutated LLM scan
                                                 outputs.

    Output layout:
      {result_root}/{skill}/{timestamp}_{mode}/generate_skill/{category}/
        iter_0/skills/   <- initial mutation
        iter_0/logs/     <- scanner logs (used for the detection check)
        iter_0/report/   <- comparison report
        iter_1/...       <- regeneration when the previous iter was detected
        ...
        iter_{N-1}/...   <- last iteration
    """

    import subprocess

    MAX_ITERATIONS = max_iterations

    # skill_name may be a bare name under {repo}/skills/, OR a full path to a
    # skill folder (e.g. examples/skills/sample_skill). Resolve both; use the
    # basename as the result-tree key so output never lands INSIDE the skill
    # directory (which would make the copytree below recurse infinitely).
    _skill_arg = Path(skill_name)
    skill_dir  = _skill_arg.resolve() if (_skill_arg / "SKILL.md").is_file() else (_REPO_ROOT / "skills" / skill_name)
    skill_key  = skill_dir.name
    # result_root: overridable from the CLI via --result-dir, so different
    # model experiments can be saved into separate roots.
    _result_root = Path(result_root) if result_root else (_REPO_ROOT / "result")

    # Pre-compute base_dir so it can be used in the log-file path.
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Encode the experiment mode in the folder name for at-a-glance triage.
    if use_select_attacks and not use_llm_detect:
        mode_suffix = "select"
    elif use_select_attacks and use_llm_detect:
        mode_suffix = "select_llm-detect"
    elif not use_select_attacks and not use_llm_detect:
        mode_suffix = "no-select"
    else:  # not use_select_attacks and use_llm_detect
        mode_suffix = "no-select_llm-detect"
    run_id      = f"{timestamp}_{mode_suffix}"
    base_dir    = _result_root / skill_key / run_id
    base_dir.mkdir(parents=True, exist_ok=True)

    llm_detect_label = "+LLM-detect" if use_llm_detect else ""
    mode_label  = ("select-on" if use_select_attacks else "select-off (ablation)") + llm_detect_label
    log_path    = base_dir / "run.log"
    _log_file   = _start_run_log(log_path)

    print(f"{'='*60}")
    print(f" run.log -> {log_path}")
    print(f"{'='*60}")

    try:
        llm = create_llm(provider=provider, model_name=model_name)

        # iter_0: produce the initial mutation.
        print(f"\n{'='*60}")
        print(f" [iter_0] initial mutation: {skill_name}  [{mode_label}]")
        print(f"{'='*60}")

        result = run_skill_mutation(
            skill_dir=skill_dir,
            attack_categories_path=str(_REPO_ROOT / "docs" / "attack_categories.json"),
            provider=provider,
            model_name=model_name,
            result_root=str(_result_root),
            iteration=0,
            base_dir=base_dir,
            use_select_attacks=use_select_attacks,
        )

        print(f"\nselected attack categories: {[a['attack_category'] for a in result['selected_attacks']]}")
        print(f"scenarios generated: {len(result['attack_scenarios'])}")

        for iteration in range(MAX_ITERATIONS):
            iter_label = f"iter_{iteration}"

            # Scan ------------------------------------------------------
            print(f"\n{'-'*60}")
            print(f" [{iter_label}] scan start")
            print(f"{'-'*60}")

            skills_to_scan = [
                Path(p) for p in result.get("saved_paths", [])
                if Path(p).is_dir()
                and Path(p).name == "skills"
                and Path(p).parent.name == iter_label
            ]

            for skills_path in skills_to_scan:
                log_dir = skills_path.parent / "logs"
                cmd = [
                    sys.executable, str(_REPO_ROOT / "src" / "skill_mutator" / "scan.py"),
                    str(skills_path.resolve()),
                    "--all",
                    f"--log-dir={log_dir}",
                    "--provider", provider,
                    "--model", model_name,
                ]
                print(f"  scanning: {skills_path.relative_to(base_dir)}")
                ret = subprocess.run(cmd)
                if ret.returncode != 0:
                    print(f"  warning: some scanners failed (exit {ret.returncode})")

            # Comparison + CSV ------------------------------------------
            print(f"\n[{iter_label}] comparing and writing CSV ...")
            csv_path = _result_root / f"comparison_{skill_dir.name}.csv"
            build_comparison_csv(
                result=result,
                original_skill_dir=skill_dir,
                baseline_root=_REPO_ROOT / "baseline_result",
                csv_path=csv_path,
                llm=llm,
                iteration=iteration,
                llm_provider=provider,
                llm_model=model_name,
                llm_mode=llm_mode,
            )
            print(f"[{iter_label}] CSV written: {csv_path}")

            # Detection check -------------------------------------------
            detected = _get_detected_categories(result, iter_label, use_llm_scanner=use_llm_detect)
            print(f"\n[{iter_label}] detected categories: {detected if detected else '(none)'}")

            if not detected:
                print(f"[{iter_label}] no detection -> loop ends")
                break

            if iteration == MAX_ITERATIONS - 1:
                print(f"[{iter_label}] reached max iterations -> loop ends")
                break

            # Regenerate -----------------------------------------------
            next_iter = iteration + 1
            print(f"\n{'-'*60}")
            print(f" [iter_{next_iter}] regenerating detected categories: {detected}")
            print(f"{'-'*60}")

            result = refine_skill_mutation(
                prev_result=result,
                original_skill_dir=skill_dir,
                attack_categories_path=str(_REPO_ROOT / "docs" / "attack_categories.json"),
                provider=provider,
                model_name=model_name,
                iteration=next_iter,
                detected_categories=detected,
                base_dir=base_dir,
            )

        print(f"\n{'='*60}")
        print(f" done: {skill_name} (final iter: {result.get('iteration', 0)})")
        print(f" results: {base_dir}")
        print(f" log:     {log_path}")
        print(f"{'='*60}")

    finally:
        _stop_run_log(_log_file)


if __name__ == "__main__":
    import argparse as _argparse
    _parser = _argparse.ArgumentParser(description="SkillMutator: mutate and scan one skill.")
    _parser.add_argument("skill", nargs="?", default="pdf",
                         help="Subfolder name under skills/ (default: pdf).")
    _parser.add_argument(
        "--no-select", action="store_true",
        help="Skip node_select_attacks (ablation: all attack categories).",
    )
    _parser.add_argument(
        "--use-llm-detect", action="store_true",
        help="Include the LLM-scanner verdict in the refinement trigger "
             "(default: only ss/snyk verdicts are used).",
    )
    _parser.add_argument(
        "--iterations", "-n",
        type=int,
        default=3,
        help="Maximum iterations (default: 3; iter_0 .. iter_{N-1}).",
    )
    _parser.add_argument(
        "--result-dir",
        default=None,
        help="Top-level output directory (default: {repo}/result). Use a "
             "per-model directory to keep experiments separate "
             "(e.g. experiments/gpt-4.1/result).",
    )
    _parser.add_argument(
        "--model",
        default="gpt-5.4-mini",
        help="Mutation-generation LLM model (default: gpt-5.4-mini).",
    )
    _parser.add_argument(
        "--provider",
        default="openai",
        help="LLM provider (default: openai).",
    )
    _parser.add_argument(
        "--llm-mode",
        default="direct",
        choices=["direct", "compare", "both"],
        help="LLM detection style: 'direct' (default; the LLM judges the "
             "mutated scan MD directly), 'compare' (baseline vs mutated diff), "
             "or 'both' (run both; refinement feedback uses 'direct').",
    )
    _args = _parser.parse_args()
    example_skill_mutation(
        _args.skill,
        use_select_attacks=not _args.no_select,
        use_llm_detect=_args.use_llm_detect,
        max_iterations=_args.iterations,
        result_root=_args.result_dir,
        model_name=_args.model,
        provider=_args.provider,
        llm_mode=_args.llm_mode,
    )