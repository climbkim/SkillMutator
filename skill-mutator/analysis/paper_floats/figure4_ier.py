#!/usr/bin/env python3
"""Paper Figure 4 — per-iteration detection under Iterative Evasion Refinement.

Builds the trajectory CSV, then renders the figure (needs matplotlib)."""
import sys, os, subprocess, shutil
sys.path.insert(0, os.path.dirname(__file__))
from _common import run_builder, ANALYSIS, OUT
SLUG = "figure4_ier"
rc = run_builder(
    "rq2/scripts/build_tab_iter_trajectory.py",
    ["tab_iter_trajectory.csv"],
    "Figure 4 — IER per-iteration dynamics", SLUG,
    {"tab_iter_trajectory.csv": "figure4_ier.csv"},
)
if rc == 0:
    plot = ANALYSIS / "rq2/scripts/plot_iter_trajectory.py"
    subprocess.call([sys.executable, plot.name], cwd=plot.parent)
    dst = OUT / SLUG; dst.mkdir(parents=True, exist_ok=True)
    for f in (plot.parent / "outputs").glob("fig_iter_trajectory.*"):
        shutil.copyfile(f, dst / ("figure4_ier" + f.suffix))
        print(f"    -> outputs/{SLUG}/figure4_ier{f.suffix}")
raise SystemExit(rc)
