# 1a — GT fragment automated comparison results

- scope: `gpt-5.4 / select / last_good_iter`, **76 cells**
- total injected fragments: **199** (avg 2.6 per cell)
- fragment match: **199/199 = 100.0%**
- cells fully passing (PASS): **76/76 = 100.0%**
- of those, GT-truncated (1,500-char cap) fragments: **48/199 = 24.1%** (affected cells 40/76)

> **Caveat.** A truncated fragment matches the actual content exactly up to the cap point, but the content after that is missing from the GT. The judge scored the scanner output looking only at this truncated GT.

## Fragment-level matching stage

| status | n | % | meaning |
|---|---|---|---|
| `exact` | 151 | 75.9% | exact match after CRLF normalization |
| `truncated_exact` | 48 | 24.1% | exact match up to the `...[truncated]` marker (GT 1,500-char cap) |

## Cell-level verdict

| verdict | n | % |
|---|---|---|
| PASS | 76 | 100.0% |

## No mismatches — all fragments confirmed in the actual content
