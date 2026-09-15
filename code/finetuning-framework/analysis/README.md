# analysis/

Paper Finding 5 / Finding 6 reproduction tables and the v2 GPT-5.4 judge used to
adjudicate scanner outputs.

```
analysis/
├── judge.py             # single-source-of-truth GPT-5.4 v2 judge prompt
├── parsers.py           # scan.md / verdict-json parsers (lifted from the mutation package)
├── rq3/scripts/
│   └── build_tab_finetune.py        # cross-family detection table (Finding 5 / Figure 5)
└── rq4/scripts/
    └── build_tab_phase_ablation.py  # P1 / P12 / P123 / P1234 ablation (Finding 6 / Table VI)
```

## How to use the judge

```python
from skill_scanner_finetune.analysis.judge import judge_call

verdict = judge_call(
    skill="my-skill",
    category="Information Gathering",
    title="my scenario title",
    disguise="",
    injected_snippet=open("injected_content.md").read(),
    scan_text=open("scan.md").read(),
)
# -> {"detected": True/False, "confidence": 0.0..1.0, "reason": "..."}
```

The judge expects `OPENAI_API_KEY` in the environment.

## How to build the tables

Each variant (data-directory suffix; `D3-noprefill`, `D3-prefill`, ablations
`D3-P1` … `D3-P1234`) should be evaluated end-to-end and produce a
`judge_summary.csv` of the form

| skill | category | cat_folder | iter | detected | confidence | reason |

with one row per evaluation scenario. The `D3-` prefix is the legacy
on-disk data-directory tag; the table-generation scripts emit paper-facing
display labels (no-prefill / prefill, Phase 1–4) for the LaTeX output.
Then aggregate:

```bash
# Cross-family (paper Finding 5 / Figure 5)
python analysis/rq3/scripts/build_tab_finetune.py \
       --root <fine-tuning-rq3-eval-root>

# Phase ablation (paper Finding 6 / Table VI)
python analysis/rq4/scripts/build_tab_phase_ablation.py \
       --root <phase-ablation-eval-root>
```

The `build_tab_phase_ablation.py` runner is a thin wrapper around the same
`judge_summary.csv` pattern — see `analysis/rq3/scripts/build_tab_finetune.py`
for the template.
