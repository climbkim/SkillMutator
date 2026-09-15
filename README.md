# SkillMutator

**Benchmarking and defending language-and-code cross-modal attacks on LLM Agent Skills.**

SkillMutator adversarially mutates LLM Agent Skills (a `SKILL.md` plus its helper
code) to inject malicious behavior across the language and code modalities, then
measures whether rule-based, commercial, and LLM-based scanners catch it. As a
defense it distills a small local scanner: a fine-tuned 7B model trained by a
four-phase reasoning-trajectory distillation that reaches frontier detection at a
fraction of the cost.

Highlights:

- A staged mutation pipeline: skill analysis, stealth-aware attack selection,
  scenario generation, skill mutation, and iterative evasion refinement, covering
  13 attack categories.
- A pluggable multi-scanner harness: our LLM scanner, `skill-security-scan`, Snyk
  Agent Scan, and held-out third-party scanners.
- A fine-tuning framework that distills a frontier teacher's structured analysis
  into a local 7B scanner reaching 88.2% detection (n=76), matching or exceeding
  frontier proprietary scanners. Released LoRA adapters are on Hugging Face.

## Layout

```
code/    runnable system
  skillmutator/          mutation + scan pipeline (self-contained): src/skill_mutator/
                         (process + scanners), scripts/, analysis/, examples/, run.sh
  finetuning-framework/  4-phase distillation + local 7B scanner (see its docs/)
  external_scanners/     held-out third-party scanner harness
  docs/, requirements.txt, pyproject.toml
data/    benchmark data (scanner verdicts + aggregates)
  skills/        self-authored sample skill + SOURCES.csv (third-party skills attributed)
  clawhub/       ClawHub corpus as URL metadata
  paper_shared/  judge verdicts, aggregates, GT validation, cross-family judge
```

See [`code/README.md`](code/README.md) for the code walkthrough, the
paper-to-code map, and how to plug in another scanner.

## Quick start

```bash
cd code
pip install -r requirements.txt        # add `pip install .[finetune]` for the GPU scanner stack
export OPENAI_API_KEY=...               # or put it in a local .env

cd skillmutator && ./run.sh             # mutate a sample skill -> scan -> build tables
```

The fine-tuned LoRA adapters (four base families) are on Hugging Face:
<https://huggingface.co/climbkim/skillmutator-scanner-adapters>

## Responsible use

The mutated skills embed injected malicious instructions and are intended ONLY as
scanner inputs in an isolated environment. Do not install or execute them against
a live agent or on a machine with sensitive data. To avoid enabling misuse, the
malicious mutated skills, scanner outputs that quote them, and the full training
corpus are **not redistributed**; `data/` ships only scanner verdicts and
aggregates. Third-party host skills and the ClawHub corpus are referenced by URL
and attribution, not copied.

## Citation

```bibtex
@inproceedings{skillmutator2026,
  title     = {SkillMutator: Benchmarking and Defending Language-and-Code Cross-modal Attacks on LLM Agent Skills},
  booktitle = {Annual Computer Security Applications Conference (ACSAC)},
  year      = {2026}
}
```

## License

MIT. Only our own `llm_scanner` is bundled; the third-party scanners are
installed from their own sources under their own licenses.
