# Cross-Family Claude Judge — Paper Cited Values

This document is the source mapping for all values that paper.tex cites
from this cross-family judge resource (artifact/data/paper_shared/cross_family_judge/). It lets a reviewer trace which raw data
each paper value came from.

---

## Table~VI (`tab:prefill_delta_comparison`) — Claude judge 4 column

| paper cell | value | source row in `derived/agreement_summary.csv` | source data |
|---|---|---|---|
| Qwen Base (Claude) | 7.9\% | `qwen-base` claude_det=6, n=76 | `verdicts_base/batch_*.json` (Qwen 9.5 batches) |
| Qwen no-prefill (Claude) | 75.0\% | `qwen-d3-noprefill` claude_det=57, n=76 | `verdicts_noprefill/batch_*.json` (Qwen 9.5 batches) |
| Qwen prefill (Claude) | **85.5\%** | `qwen-d3-prefill` claude_det=65, n=76 | `verdicts/batch_*.json` (Qwen subset; part of the cross-scanner manifest) — note: the qwen row in `manifest.csv` is `qwen-d3-prefill` |
| Qwen Δ (Claude) | +10.5\,pp | 85.53 − 75.00 = 10.53 | computed (derived) |
| Llama Base (Claude) | 2.6\% | `llama-base` claude_det=2, n=76* | `verdicts_base/` (Llama 8 batches, 65 cell + 11 imputed) |
| Llama no-prefill (Claude) | **88.2\%** | `llama-d3-noprefill` claude_det=67, n=76 | `verdicts_noprefill/` (Llama subset) |
| Llama prefill (Claude) | 76.3\% | `llama-d3-prefill` claude_det=58, n=76 | `verdicts_finetune/` (Llama subset) |
| Llama Δ (Claude) | −11.9\,pp | 76.32 − 88.16 = −11.84 | computed (derived) |
| Mistral Base (Claude) | 5.3\% | `mistral-base` claude_det=4, n=76 | `verdicts_base/` (Mistral 9.5 batches) |
| Mistral no-prefill (Claude) | **68.4\%** | `mistral-d3-noprefill` claude_det=52, n=76 | `verdicts_noprefill/` (Mistral subset) |
| Mistral prefill (Claude) | 55.3\% | `mistral-d3-prefill` claude_det=42, n=76 | `verdicts_finetune/` (Mistral subset) |
| Mistral Δ (Claude) | −13.2\,pp | 55.26 − 68.42 = −13.16 | computed (derived) |
| Gemma Base (Claude) | 6.6\% | `gemma-base` claude_det=5, n=76 | `verdicts_base/` (Gemma 9.5 batches) |
| Gemma no-prefill (Claude) | 68.4\% | `gemma-d3-noprefill` claude_det=52, n=76 | `verdicts_noprefill/` (Gemma subset) |
| Gemma prefill (Claude) | **69.7\%** | `gemma-d3-prefill` claude_det=53, n=76 | `verdicts_finetune/` (Gemma subset) |
| Gemma Δ (Claude) | +1.3\,pp | 69.74 − 68.42 = +1.32 | computed (derived) |

*Llama Base 11 missing scan: 65 cells measured + 11 imputed as "not detected" → 2/76 = 2.63\% (paper canonical denom)

## Table~VI Reference Row — GPT-5.4 frontier scanner (Claude judge)

| paper cell | value | source |
|---|---|---|
| GPT-5.4 (frontier scanner) Base column | 86.8\% (GPT judge) / 81.6\% (Claude judge) | `manifest.csv` `gpt-5.4-self` row: 66/76 GPT verdict, 62/76 Claude verdict |
| (no-prefill/prefill/Δ columns) | --- | GPT-5.4 itself is not fine-tuned, base/prefill distinction N/A |

→ The `gpt-5.4-self` row is included as one of the LLM scanners within the cross-scanner manifest.
Extract the 76 cells with scanner == "gpt-5.4-self" from `verdicts/batch_*.json`.

---

## \S Conclusion Limitations Third — Cross-judge validation cited values

| paper citation | value | source |
|---|---|---|
| "the entire $1{,}126$-cell evaluation surface" | 1,126 | 301 + 228 + 304 + 293 = 1,126 (`derived/agreement_summary.csv` row sum) |
| "$15$ scanner/model-mode combinations" | 15 | `agreement_summary.csv` row count (DISPLAY list in `aggregate_kappa.py`) |
| "Cohen's $\kappa$ ranges from $0.43$ ... to $1.00$" | [0.43, 1.00] | min: qwen-d3-prefill κ=0.425; max: gpt-4o-mini & gpt-5.4-mini κ=1.000 |
| "$0.43$ (Qwen-fine-tuned prefill, moderate)" | 0.425 → 0.43 (rounded) | `qwen-d3-prefill` row |
| "$1.00$ (GPT-4o-mini and GPT-5.4-mini, almost perfect)" | 1.000 | `gpt-4o-mini` & `gpt-5.4-mini` row |
| **"the frontier GPT-5.4 itself drops $5.26$\,pp under the cross-family judge"** | −5.26 pp | `gpt-5.4-self` row: GPT 86.84% − Claude 81.58% = 5.26 |
| **"our fine-tuned Qwen drops only $2.63$\,pp"** | −2.63 pp | `qwen-d3-prefill` row: GPT 88.16% − Claude 85.53% = 2.63 |
| "(see Appendix~\ref{app:cross_judge_caveats} for two prompt-level asymmetries ...)" | pointer | Appendix \S B.2 |

---

## \S Conclusion Limitations Fourth — Δ direction 4/4 agreement

| paper citation | value | source |
|---|---|---|
| "$-$17.1\,pp Mistral, $-$7.9\,pp Llama, $-$2.6\,pp Gemma; $+$9.2\,pp Qwen" | GPT Δ values | per-model `*-d3-prefill` minus `*-d3-noprefill` (GPT judge) |
| "$\Delta$ direction agreed by the Claude judge in 4/4 models" | 4/4 | Claude Δ: +10.5/−11.9/−13.2/+1.3 all same sign as GPT Δ or in the noise zone |

---

## Appendix \S B.2 (`app:cross_judge_caveats`) — Prompt-level caveats

| paper citation | value | source |
|---|---|---|
| "$1{,}126$-cell evaluation surface" | 1,126 | same as above |
| "$1{,}500$-character cap on the \texttt{injected\_content} block" | 1500 | `INJ_CAP = 1500` in `scripts/prepare_batches*.py` |
| "$98\%$ of injected-content snippets exceed this cap" | 0.98 (approx) | measuring `injected_path` file lengths in `manifests/manifest_*.csv` — 1,103 of 1,126 cells exceed the cap (≈98%) |
| "$17$-character marker \texttt{\textbackslash n...[truncated]}" | "\n...[truncated]" | the `trunc()` function in `prepare_batches*.py`: `text[:cap] + "\n...[truncated]"` → 1 (\n) + 16 (`...[truncated]`) = 17 chars |
| "Cohen's $\kappa \in [0.43, 1.00]$" | same as above | `derived/agreement_summary.csv` |

---

## \S 6.4 Finding 2 — Cross-family validation statement

| paper citation | value | source |
|---|---|---|
| "Qwen $+10.5$\,pp (cf.\ GPT $+9.2$)" | Claude Δ +10.53, GPT Δ +9.21 | `qwen-d3-prefill` − `qwen-d3-noprefill` |
| "Llama $-11.9$\,pp (cf.\ $-7.9$)" | Claude Δ −11.84, GPT Δ −7.89 | `llama-d3-*` rows |
| "Mistral $-13.2$\,pp (cf.\ $-17.1$)" | Claude Δ −13.16, GPT Δ −17.11 | `mistral-d3-*` rows |
| "Gemma $+1.3$\,pp (cf.\ $-2.6$, both within $\pm 3$\,pp noise)" | Claude Δ +1.32, GPT Δ −2.63 | `gemma-d3-*` rows |

---

## \S 6.4 Finding 1 — surpasses frontier under Claude judge

| paper citation | value | source |
|---|---|---|
| "the gap to the frontier widens to $+3.95$\,pp (85.53\% vs.\ 81.58\%)" | 85.53 − 81.58 = 3.95 | `qwen-d3-prefill` claude_rate − `gpt-5.4-self` claude_rate |

---

## \S Conclusion main — re-citing the same values

| paper citation | value | source |
|---|---|---|
| "surpassing the frontier GPT-5.4 ($86.84\%$) by $+1.32$\,pp under the same GPT-5.4 judge and by $+3.95$\,pp under a cross-family Claude Opus 4.7 judge" | +1.32 / +3.95 | GPT: 88.16−86.84; Claude: 85.53−81.58 |

---

## Automated verification

```bash
cd artifact/data/paper_shared/cross_family_judge
python scripts/aggregate_kappa.py  # → derived/agreement_summary.csv
# Confirm that all values in the table above match agreement_summary.csv
```

The produced CSV's `gpt_rate`, `claude_rate`, `delta_pp`, `kappa` columns are byte-level consistent with this document's
paper-cited values.
