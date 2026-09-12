# Paper floats — per-float builders (mutation side)

Each script here is a thin, **paper-labelled** wrapper around one builder under
`analysis/rq1|rq2/scripts/`. It runs that builder (which reads the
mutated+scanned data tree at `$SKILLMUTATOR_DATA_ROOT`) and copies the result
into `outputs/` under the paper's float name. Labels are aligned to the paper,
not the builders' legacy local numbering.

| Script | Paper float | Underlying builder |
|---|---|---|
| `table3_refusal.py`       | **Table III** — safety-refusal summary        | `rq1/scripts/build_tab2_refusal_summary.py` |
| `table4_cross_scanner.py` | **Table IV** — cross-scanner detection matrix  | `rq1/scripts/build_tab1_cross_matrix.py` |
| `table5_select.py`        | **Table V** — select vs no-select              | `rq2/scripts/build_tab_select_vs_noselect.py` |
| `figure4_ier.py`          | **Figure 4** — IER per-iteration dynamics      | `rq2/scripts/build_tab_iter_trajectory.py` + `plot_iter_trajectory.py` |

Run them after a mutation+scan run (see `../../run.sh`), or individually with
`$SKILLMUTATOR_DATA_ROOT` pointing at a populated data tree. Outputs land in
`outputs/` (`table3_*`, `table4_*`, `table5_*`, `figure4_*`).

The fine-tuned-scanner floats (Figures 5–6, Tables VI/VII/X/XI) are built on the
fine-tuning side — see `../../../finetuning-framework/`.
