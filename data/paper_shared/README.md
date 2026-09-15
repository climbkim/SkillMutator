# `paper_shared/` — shared judge configs, verdicts, and validation data

Cross-cutting data used by more than one claim/RQ. Verdict-level and aggregate
only — no injected payloads; raw scan trees are **not redistributed** (see
`ETHICS.md`).

- `base_models/` — base-model + LoRA adapter manifest (adapters on Hugging Face).
- `cross_family_judge/` — Claude-vs-GPT-5.4 judge agreement (verdicts + kappa/CI).
- `gt_validation/` — ground-truth fragment/coverage validation (aggregates/reports).

Each subdirectory carries a packaging note; see it for scope and how results were produced.
