# evaluate/

> Single source of truth for reproducing every paper table and figure from the
> pipeline-generated output trees.

This folder consolidates the evaluation scripts that take outputs produced by
[`skill-mutator`](../skill-mutator) (mutation pipeline + cross-scanner sweep)
and [`skill-scanner-finetune`](../skill-scanner-finetune) (4-phase distillation
and fine-tuned scanner inference), and emits the CSV / TeX / PDF artifacts that
appear in the paper.

## Layout

```
evaluate/
├── README.md                       # this file
├── lib/                            # shared utility library
│   ├── data_access.py              # walks the SkillMutator-data tree
│   ├── parsers.py                  # scan.md / verdict.json / judge JSON parsers
│   ├── refusal.py                  # classification field → refusal-free re-pin
│   └── judge.py                    # GPT-5.4 v2 judge invocation
├── scripts/
│   ├── tables/
│   │   ├── table3_cross_matrix.py          # paper Table III
│   │   ├── table4_refusal_summary.py       # paper Table IV
│   │   ├── table5_select_vs_noselect.py    # paper Table V
│   │   ├── table6_prefill_delta.py         # paper Table VI
│   │   ├── table7_phase_ablation.py        # paper Table VII
│   │   ├── appendix_b1_baseline.py         # paper Appendix B.1
│   │   └── appendix_b2_cell_matrix.py      # paper Appendix B.2
│   ├── figures/
│   │   ├── figure_ier_dynamics.py          # IER per-iter detection dynamics
│   │   └── figure_fp_per_cat.py            # per-category FP cell count
│   └── stats/
│       ├── compute_kappa.py                # Cohen's κ cross-judge agreement
│       └── compute_paper_cited_values.py   # verify paper-cited values
└── outputs/                                # generated artifacts land here
```

## Paper artifact → script mapping

### Tables

| Paper artifact            | Section  | Build script                                  | Output                              |
|---------------------------|----------|-----------------------------------------------|-------------------------------------|
| Table III (`tab:cross_matrix`)             | §6.2    | `scripts/tables/table3_cross_matrix.py`       | `outputs/table3_cross_matrix.{csv,tex}` |
| Table IV (`tab:refusal_i4_summary`)        | §6.1    | `scripts/tables/table4_refusal_summary.py`    | `outputs/table4_refusal_summary.{csv,tex}` |
| Table V (`tab:select_vs_noselect`)         | §6.3.1  | `scripts/tables/table5_select_vs_noselect.py` | `outputs/table5_select_vs_noselect.{csv,tex}` |
| Table VI (`tab:prefill_delta_comparison`)  | §6.4    | `scripts/tables/table6_prefill_delta.py`      | `outputs/table6_prefill_delta.{csv,tex}` |
| Table VII (`tab:finetune_rq2`)             | §6.4    | `scripts/tables/table7_phase_ablation.py`     | `outputs/table7_phase_ablation.{csv,tex}` |
| Appendix B.1 (`tab:baseline_aggregate`)    | §B.1    | `scripts/tables/appendix_b1_baseline.py`      | `outputs/appendix_b1_baseline.{csv,tex}` |
| Appendix B.2 (`tab:cell_metrics`)          | §B.2    | `scripts/tables/appendix_b2_cell_matrix.py`   | `outputs/appendix_b2_cell_matrix.{csv,tex}` |

### Figures

| Paper artifact            | Section  | Build script                              | Output                              |
|---------------------------|----------|-------------------------------------------|-------------------------------------|
| `fig:ier_dynamics`        | §6.3.2   | `scripts/figures/figure_ier_dynamics.py`  | `outputs/figure_ier_dynamics.{pdf,png,csv}` |
| `fig:fp_per_cat`          | §B.2     | `scripts/figures/figure_fp_per_cat.py`    | `outputs/figure_fp_per_cat.{pdf,png,csv}` |

### Statistical validations

| Paper claim                        | Section  | Script                              |
|------------------------------------|----------|-------------------------------------|
| Cohen's $\kappa \in [0.43, 1.00]$ | §7 Limit. 3 | `scripts/stats/compute_kappa.py` |
| All cited values cross-check       | global   | `scripts/stats/compute_paper_cited_values.py` |

## Configuration

Every script reads from a unified data tree. Set the root via env var:

```bash
export SKILLMUTATOR_DATA_ROOT=/path/to/Skillmutator-data
export FINETUNE_SCAN_ROOT=/path/to/finetune-scan-outputs    # for tables VI / VII
export FINETUNE_BASELINE_ROOT=/path/to/finetune-baseline    # for Appendix B.1 / B.2
```

Data tree layout expected at `SKILLMUTATOR_DATA_ROOT`:

```
<oracle>/<mode>/<skill>/<cat_folder>/iter_K/
├── meta.json                {oracle, mode, skill, ..., classification}
├── injected_content.md      attack ground truth (≤ 1500 chars/file)
├── ss/{report.md, verdict.json}        skill-security-scan output
├── snyk/{report.md, verdict.json}      Snyk Agent Scan output
└── llm/<scanner>/{scan.md, judge_v2.json, verdict.json}
                             LLM scanner output + GPT-5.4 v2 judge verdict
```

`classification` is one of `normal` / `silent_failure` / `partial_refusal` /
`explicit_refusal` / `missing`. Only `normal` iters contribute to the paper's
re-pinned final evaluation; refusal iters fall back to the latest `normal` iter
≤ current.

## Quickstart

```bash
# Install minimal deps
pip install -r requirements.txt   # csv (stdlib), matplotlib, pyyaml, openai (judge only)

# Reproduce every paper artifact (assumes data trees populated)
bash reproduce_all.sh

# Or run a single artifact
python scripts/tables/table3_cross_matrix.py
python scripts/figures/figure_ier_dynamics.py
```

Each script writes to `outputs/` and prints a one-line summary on success.

## Re-pin semantics (paper Table III / VI canonical values)

The paper's headline numbers use **refusal-free re-pinning**: for each
(skill, category) scenario, the evaluation iter is the latest iter $j \le K$
whose `meta.json` has `classification == "normal"`. Scenarios with no normal
iter ≤ K are excluded for that iter's cell.

This is implemented in `lib/refusal.py` and exposed via the helper
`aggregate_scenario_final(...)` which all table builders use, so the same
re-pin logic is applied everywhere.

## Citation

```bibtex
@inproceedings{skillmutator2026,
  title  = {<paper title — to fill in>},
  author = {<authors — anonymized>},
  year   = {2026},
}
```

## License

MIT. See `../skill-mutator/LICENSE`.
