> **Artifact packaging note.** This directory ships the **verdict-level and
> aggregate outputs** cited in the paper. The author-side build scripts that
> regenerate them read the raw scanner/scan tree and injected-mutation content,
> which are **not redistributed** — the malicious mutations cannot be published
> (see `use.txt` / `ETHICS.md`). For runnable, self-contained reproduction use
> the per-claim scripts under `claims/`. Raw data is available from the authors
> on request (climbkim@kaist.ac.kr).
# Cross-Family Claude Judge — Shared Resource

## (1) Purpose

This shared resource takes the detection results produced by the paper-canonical GPT-5.4 judge
and re-judges them with a **cross-family Claude Opus 4.7 judge** under a byte-identical prompt,
validating self-judge bias. Over a total of **1,126 cell** ($15$ scanner/model-mode rows),
it computes the agreement between the GPT-5.4 verdict and Claude verdict, and Cohen's $\kappa$.

Because it reinforces several paper tables at once, it is placed as a shared resource rather than a single table folder
(the same paradigm as the judge script (not redistributed) holding the GPT-5.4 judge code).

## (2) Affected paper locations

| paper location | cited data |
|---|---|
| Table~VI (`tab:prefill_delta_comparison`) Claude judge 4 column × 4 base model | base + finetune-prefill + finetune-noprefill measured values (825 cells) |
| Table~VI GPT-5.4 reference row Claude column ($81.58\%$) | the `gpt-5.4-self` row of the cross-scanner manifest (76 cells) |
| \S Conclusion Limitations Third — Cohen's $\kappa \in [0.43, 1.00]$ | `derived/agreement_summary.csv` 15-row aggregate |
| \S Conclusion Limitations Third — $5.26$\,pp drop / $2.63$\,pp drop | `gpt-5.4-self` row Δ / `qwen-d3-prefill` row Δ |
| Appendix \S B.2 (`app:cross_judge_caveats`) — $1{,}500$-char cap, $17$-char marker | `scripts/prepare_batches_*.py` (`SCAN_CAP`, `INJ_CAP`, `trunc()` marker) |

## (3) Data structure

| folder/file | content |
|---|---|
| `manifest.csv` | cross-scanner manifest (301 cells, 4 LLM scanners) |
| `manifest_finetune.csv` | finetune-prefill manifest (228 cells, 3 fine-tuned LoRA models) |
| `manifest_noprefill.csv` | finetune-noprefill manifest (304 cells, 4 fine-tuned LoRA models) |
| `manifest_base.csv` | base-model manifest (293 cells, 4 un-tuned base models) |
| `batches/`, `batches_finetune/`, `batches_noprefill/`, `batches_base/` | 142 input batch JSONs (BATCH_SIZE=8): 38 + 29 + 38 + 37. Each batch has ≤8 cells' system+user prompt + paper-canonical GPT-5.4 verdict (for downstream comparison). |
| `verdicts/`, `verdicts_finetune/`, `verdicts_noprefill/`, `verdicts_base/` | 142 Claude verdict JSONs (1,126 cell). Each verdict is a `{case_id, scanner, detected, confidence, reason}` schema. |
| `scripts/build_manifest{,_finetune,_noprefill,_base}.py` | manifest builder (oracle scenario tree × per-scanner judge CSV matching) |
| `scripts/prepare_batches{,_finetune,_noprefill,_base}.py` | manifest → batch JSON generation (`SCAN_CAP=12000`, `INJ_CAP=1500`, marker `\n...[truncated]`) |
| `scripts/aggregate_kappa.py` | 4 manifest + 4 verdict folders → per-scanner Cohen's $\kappa$, agreement, 2x2 confusion |
| `derived/agreement_summary.csv` | 15 row × 12 column aggregate (n, det, rate, Δ, agreement, κ, TT/TF/FT/FF) |
| `derived/agreement_report.md` | auto-generated markdown report |

### 1,126 cell distribution

| Manifest | cells | scanners |
|---|---|---|
| cross-scanner (`manifest.csv`) | 301 | gpt-4o-mini, gpt-5.4-mini, gpt-5.4-self, claude-opus-4.7-self |
| finetune-prefill (`manifest_finetune.csv`) | 228 | llama-d3-prefill, mistral-d3-prefill, gemma-d3-prefill |
| finetune-noprefill (`manifest_noprefill.csv`) | 304 | qwen-d3-noprefill, llama-d3-noprefill, mistral-d3-noprefill, gemma-d3-noprefill |
| base (`manifest_base.csv`) | 293 | qwen-base, llama-base (65), mistral-base, gemma-base |
| **Total** | **1,126** | — |

## (4) Reproduction commands

```bash
cd artifact/data/paper_shared/cross_family_judge
# (1) regenerate manifest (requires canonical scenario tree + per-scanner judge CSV)
python scripts/build_manifest.py
python scripts/build_manifest_finetune.py
python scripts/build_manifest_noprefill.py
python scripts/build_manifest_base.py

# (2) regenerate batches (input prompts)
python scripts/prepare_batches.py
python scripts/prepare_batches_finetune.py
python scripts/prepare_batches_noprefill.py
python scripts/prepare_batches_base.py

# (3) With the Claude Opus 4.7 sub-agent, take batches/<NAME>/batch_*.json as input
#     and produce verdicts as verdicts/<NAME>/batch_*.json
#     (performed in the Claude Code sub-agent environment, not an external API call)

# (4) compute Cohen's κ
python scripts/aggregate_kappa.py  # → derived/agreement_summary.csv + derived/agreement_report.md
```

Before running, set `OUT_DIR` to `cross_family_judge/` and point `sys.path` at the
`skillmutator_utils` module.

## (5) Dependencies (source scan tree, not redistributed)

| resource | purpose |
|---|---|
| the source scan tree (not redistributed) — per-cell meta.json / injected_content.md | the manifest builder extracts scenario meta and injected content |
| the judge script (not redistributed) | paper-canonical GPT-5.4 judge call code (for reference; the Claude judge prompt keeps a byte-identical copy in `JUDGE_SYSTEM`, `JUDGE_USER_TEMPLATE` within build_manifest_*.py) |
| `table3_cross_scanner_matrix/judge/*.csv` | gpt54_detected/confidence/reason source of the cross-scanner manifest |
| `table6_finetune_base_models/judge/*.csv` | gpt54_detected/confidence/reason source of the finetune/base manifest |

## (6) Verification status

✅ **Verified** — 1,126/1,126 cells judged, $\kappa \in [0.43, 1.00]$,
all detection orderings preserved across two judges.

See `derived/agreement_report.md` for detailed verification results.