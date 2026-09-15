# C2 Judge Bias — Full Agreement Report (cross-scanner + finetune)

Cross-family judge: **Claude (sub-agent, Opus 4.7)** vs paper-canonical **GPT-5.4 judge**.
Total cells: 1126 across 15 scanners.

## Per-scanner agreement

| Scanner | n | GPT det | Claude det | Δ (pp) | Agree | κ | Label |
|---|---|---|---|---|---|---|---|
| gpt-4o-mini | 73 | 18 (24.66%) | 18 (24.66%) | +0.00 | 100.00% | 1.000 | almost perfect |
| gpt-5.4-mini | 76 | 60 (78.95%) | 60 (78.95%) | +0.00 | 100.00% | 1.000 | almost perfect |
| gpt-5.4-self | 76 | 66 (86.84%) | 62 (81.58%) | -5.26 | 94.74% | 0.803 | almost perfect |
| qwen-base | 76 | 13 (17.11%) | 6 (7.89%) | -9.21 | 90.79% | 0.587 | moderate |
| qwen-d3-noprefill | 76 | 60 (78.95%) | 57 (75.00%) | -3.95 | 82.89% | 0.519 | moderate |
| qwen-d3-prefill | 76 | 67 (88.16%) | 65 (85.53%) | -2.63 | 86.84% | 0.425 | moderate |
| llama-base | 65 | 6 (9.23%) | 2 (3.08%) | -6.15 | 93.85% | 0.476 | moderate |
| llama-d3-noprefill | 76 | 63 (82.89%) | 67 (88.16%) | +5.26 | 94.74% | 0.789 | substantial |
| llama-d3-prefill | 76 | 57 (75.00%) | 58 (76.32%) | +1.32 | 93.42% | 0.821 | almost perfect |
| mistral-base | 76 | 4 (5.26%) | 4 (5.26%) | +0.00 | 97.37% | 0.736 | substantial |
| mistral-d3-noprefill | 76 | 55 (72.37%) | 52 (68.42%) | -3.95 | 96.05% | 0.905 | almost perfect |
| mistral-d3-prefill | 76 | 42 (55.26%) | 42 (55.26%) | +0.00 | 94.74% | 0.894 | almost perfect |
| gemma-base | 76 | 8 (10.53%) | 5 (6.58%) | -3.95 | 96.05% | 0.749 | substantial |
| gemma-d3-noprefill | 76 | 45 (59.21%) | 52 (68.42%) | +9.21 | 80.26% | 0.577 | moderate |
| gemma-d3-prefill | 76 | 43 (56.58%) | 53 (69.74%) | +13.16 | 81.58% | 0.611 | substantial |

## 2x2 Confusion (GPT row, Claude column)

| Scanner | TT | TF (GPT-yes Claude-no) | FT (GPT-no Claude-yes) | FF |
|---|---|---|---|---|
| gpt-4o-mini | 18 | 0 | 0 | 55 |
| gpt-5.4-mini | 60 | 0 | 0 | 16 |
| gpt-5.4-self | 62 | 4 | 0 | 10 |
| qwen-base | 6 | 7 | 0 | 63 |
| qwen-d3-noprefill | 52 | 8 | 5 | 11 |
| qwen-d3-prefill | 61 | 6 | 4 | 5 |
| llama-base | 2 | 4 | 0 | 59 |
| llama-d3-noprefill | 63 | 0 | 4 | 9 |
| llama-d3-prefill | 55 | 2 | 3 | 16 |
| mistral-base | 3 | 1 | 1 | 71 |
| mistral-d3-noprefill | 52 | 3 | 0 | 21 |
| mistral-d3-prefill | 40 | 2 | 2 | 32 |
| gemma-base | 5 | 3 | 0 | 68 |
| gemma-d3-noprefill | 41 | 4 | 11 | 20 |
| gemma-d3-prefill | 41 | 2 | 12 | 21 |