# Host skills — third-party originals NOT redistributed

The security **evaluation** uses **benign original Agent Skills** as hosts that
the SkillMutator pipeline mutates. These are Anthropic's officially published
skills; the paper's authors do **not** own them and therefore do **not
redistribute** them here.

## What is shipped
- `weather-cache/` — a small, **self-authored** benign sample skill (MIT, ours),
  used to illustrate the host-skill format and to drive the SkillMutator
  Pipeline demo (`artifact/code/skillmutator/run.sh`, or `./run.sh --tier 2`).
- `SOURCES.csv` — attribution for the **17 Anthropic evaluation host skills**
  (the fixed, public paper eval set; `github.com/anthropics/skills`): directory,
  `name`, per-skill `homepage`, `marketplace` (`anthropics/skills`), and the
  `license_field` from each skill's `SKILL.md`. Each skill remains under its
  original Anthropic license/terms. This is the same 17-skill set the crawler
  copies (`crawler/anthropic.py` `EVAL_17`).

The separate **community training pool** used for fine-tuning (`train-community-50`,
crawled from public registries such as ClawHub) is **not** listed here and **not**
shipped — its licenses vary per skill and it is freely substitutable. See
`artifact/code/skillmutator/docs/SKILLS_SETUP.md` for how to assemble it.

## Obtaining the originals
Each of the 17 skills is at its `homepage` under `github.com/anthropics/skills`;
the exact snapshot used in the paper is available from the corresponding author
on request (climbkim@kaist.ac.kr). The per-claim reproduction (`claims/`) does
not need the raw skills — it runs from bundled scanner-verdict CSVs.
