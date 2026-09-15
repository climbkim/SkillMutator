# `skills/` — default skill pool

This directory is the default location the pipeline looks up skills by name
(`python -m skill_mutator.main <name>` resolves `<name>` here) and the default
target of `run.sh --crawl` / `scripts/crawl_skills.py --output-dir ./skills`.

It ships **empty on purpose**: no third-party skill bodies are redistributed
(licenses vary per skill). Populate it yourself:

- one bundled sample skill lives at `examples/skills/sample_skill/` and is what
  `run.sh` mutates by default (no setup needed);
- to assemble the paper's evaluation/training pools, see `docs/SKILLS_SETUP.md`.

Drop each skill as its own sub-folder containing at least a `SKILL.md`.
