# Paper floats — per-float builders (mutation side)

Each script here is a thin, **paper-labelled** wrapper around one builder under
`analysis/rq1|rq2/scripts/`. It runs that builder (which reads the
mutated+scanned data tree at `$SKILLMUTATOR_DATA_ROOT`) and writes the result
into a **per-float subfolder** of `outputs/` — one clearly-named folder per
paper float, like the top-level `claims/` directory:

```
analysis/paper_floats/outputs/
├── table3_refusal/         table3_refusal_summary.csv, table3_refusal_per_iter.csv
├── table4_cross_scanner/   table4_cross_scanner.csv, table4_cross_scanner.tex
├── table5_select/          table5_select_vs_noselect.csv
└── figure4_ier/            figure4_ier.csv, figure4_ier.pdf, figure4_ier.png
```

| Script | Paper float | Underlying builder |
|---|---|---|
| `table3_refusal.py`       | **Table III** — safety-refusal summary        | `rq1/scripts/build_tab2_refusal_summary.py` |
| `table4_cross_scanner.py` | **Table IV** — cross-scanner detection matrix  | `rq1/scripts/build_tab1_cross_matrix.py` |
| `table5_select.py`        | **Table V** — select vs no-select              | `rq2/scripts/build_tab_select_vs_noselect.py` |
| `figure4_ier.py`          | **Figure 4** — IER per-iteration dynamics      | `rq2/scripts/build_tab_iter_trajectory.py` + `plot_iter_trajectory.py` |

`../../run.sh` runs the whole flow (mutate -> scan -> consolidate -> populate ->
build) and leaves only these per-float folders as the result. To rebuild the
floats alone from an existing data tree, set `$SKILLMUTATOR_DATA_ROOT` and run
the scripts individually.

The fine-tuned-scanner floats (Figures 5–6, Tables VI/VII/X/XI) are built on the
fine-tuning side — see `../../../finetuning-framework/`.
