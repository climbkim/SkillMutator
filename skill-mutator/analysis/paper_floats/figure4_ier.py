#!/usr/bin/env python3
"""Paper Figure 4 — per-iteration detection under Iterative Evasion Refinement.

Builds the trajectory CSV, then renders the figure."""
import sys, os, subprocess
sys.path.insert(0, os.path.dirname(__file__))
from _common import run_builder, ANALYSIS
rc = run_builder(
    "rq2/scripts/build_tab_iter_trajectory.py",
    ["tab_iter_trajectory.csv"],
    "Figure 4 — IER per-iteration dynamics",
    {"tab_iter_trajectory.csv": "figure4_ier_trajectory.csv"},
)
if rc == 0:
    plot = ANALYSIS / "rq2/scripts/plot_iter_trajectory.py"
    subprocess.call([sys.executable, plot.name], cwd=plot.parent)
    import shutil
    src = plot.parent / "outputs"
    out = os.path.join(os.path.dirname(__file__), "outputs")
    for f in src.glob("fig_iter_trajectory.*"):
        shutil.copyfile(f, os.path.join(out, "figure4_ier" + f.suffix))
        print(f"    -> outputs/figure4_ier{f.suffix}")
raise SystemExit(rc)
