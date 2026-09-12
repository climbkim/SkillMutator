"""Shared helper for the per-float builders.

Each paper-float module is a thin, paper-labelled wrapper around one of the
existing analysis builders under analysis/rq1|rq2/scripts/. It runs that builder
(which reads the mutated+scanned data tree at $SKILLMUTATOR_DATA_ROOT and writes
its CSV/TeX under its own outputs/) and copies the result into
analysis/paper_floats/outputs/ under the paper's float name.

Paper float <-> builder mapping (labels aligned to the paper, not the builders'
legacy local numbering):
    Table III  Safety-refusal summary        <- rq1/build_tab2_refusal_summary.py
    Table IV   Cross-scanner detection        <- rq1/build_tab1_cross_matrix.py
    Table V    select vs no-select            <- rq2/build_tab_select_vs_noselect.py
    Figure 4   IER per-iteration dynamics      <- rq2/build_tab_iter_trajectory.py (+ plot)
"""
from __future__ import annotations
import shutil, subprocess, sys
from pathlib import Path

ANALYSIS = Path(__file__).resolve().parents[1]          # .../skillmutator/analysis
OUT = Path(__file__).resolve().parent / "outputs"       # paper_floats/outputs


def run_builder(rel_builder: str, produced: list[str], float_label: str,
                rename: dict[str, str]) -> int:
    """Run one builder, then copy its outputs into paper_floats/outputs/ under
    paper-float names.

    rel_builder : path of the builder relative to analysis/ (its cwd at run time)
    produced    : output filenames the builder writes under its own outputs/
    float_label : e.g. "Table III — Safety-refusal summary"
    rename      : {builder_output_name: paper_float_output_name}
    """
    builder = ANALYSIS / rel_builder
    if not builder.is_file():
        print(f"[error] builder not found: {builder}", file=sys.stderr)
        return 1
    print(f"=== {float_label} ===")
    print(f"    builder: analysis/{rel_builder}")
    # Builders write to ./outputs relative to their own cwd.
    rc = subprocess.call([sys.executable, builder.name], cwd=builder.parent)
    if rc != 0:
        print(f"[error] builder failed (rc={rc}); is $SKILLMUTATOR_DATA_ROOT populated?",
              file=sys.stderr)
        return rc
    OUT.mkdir(parents=True, exist_ok=True)
    src_dir = builder.parent / "outputs"
    for name in produced:
        src = src_dir / name
        if not src.is_file():
            print(f"    [warn] expected output missing: {src}")
            continue
        dst = OUT / rename.get(name, name)
        shutil.copyfile(src, dst)
        print(f"    -> {dst.relative_to(OUT.parent)}")
    return 0
