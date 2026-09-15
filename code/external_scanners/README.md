# `external_scanners/` — held-out third-party scanner harness

Drivers that run the held-out (not-in-our-refinement-loop) third-party scanners
over the SkillMutator benchmark, used for the held-out re-evaluation.

- `run_external_scanners.py` — Sentry / Cisco / SkillScan drivers.
- `run_underhood_llm.py` — the "Under the Hood" static+LLM scanner.
- `run_llm_scanners.py` — LLM-mode scanning harness.
- `make_levels.py`, `make_summary.py` — aggregate detections into the held-out result tables.

Third-party scanner **sources are not bundled** (install them yourself); these
drivers invoke them via env-configured interpreters. The held-out evaluation
results and documentation are not bundled in this version; available from the
authors on request.
