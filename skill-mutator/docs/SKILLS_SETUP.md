# Setting up the skill collections

This repo ships **no** skills (other than one tiny smoke-test sample at `examples/skills/sample_skill/`). Reproducing the paper requires assembling two disjoint collections yourself:

1. **17 evaluation skills** — Anthropic's officially published Agent Skills.
2. **50 training skills** (30 originally crawled + 20 added in a later expansion) — community-authored skills from public registries.

The strict separation ensures no train/test contamination.

## 1. Anthropic-published skills (n = 17)

These are released by Anthropic for Claude. Clone the official repository:

```bash
mkdir -p ${SKILLMUTATOR_DATA_ROOT}/skills/eval-anthropic-17
git clone https://github.com/anthropics/skills.git /tmp/anthropic-skills
# Copy the 17 skills used in the paper. The exact names are listed below.
for s in algorithmic-art brand-guidelines canvas-design claude-api \
         doc-coauthoring docx frontend-design internal-comms \
         mcp-builder pdf pptx skill-creator slack-gif-creator \
         theme-factory web-artifacts-builder webapp-testing xlsx; do
    cp -r "/tmp/anthropic-skills/$s" "${SKILLMUTATOR_DATA_ROOT}/skills/eval-anthropic-17/"
done
```

Verify each skill has at least a `SKILL.md` plus zero or more `.py` / template files. License: see Anthropic's repository (typically Apache 2.0 or MIT, but check per skill).

## 2. Community-authored training skills (n = 50)

These were collected from public skill registries (e.g. ClawHub, GitHub topic searches, community Discord shares). The repo ships the crawler **entry point** (`scripts/crawl_skills.py`) but **not** a registry backend and **not** the skill bodies — licenses vary per skill, and scraping terms vary per registry.

To assemble your own pool of 50 community skills, you can either:

### Option A — Use the included crawler entry point

```bash
# via run.sh (populates ./skills, then mutates the pool):
./run.sh --crawl 50 --registry clawhub --skills-dir ./skills
# or directly:
python scripts/crawl_skills.py --registry clawhub --target-count 50 \
       --output-dir ${SKILLMUTATOR_DATA_ROOT}/skills/train-community-50
```

`crawl_skills.py` dispatches to `skill_mutator.crawler.<registry>` and expects a
`crawl(target_count, output_dir)` function there. **That backend is not
included** — add `src/skill_mutator/crawler/<registry>.py` implementing it for
the registry you are authorised to scrape. Until you do, the crawler exits with
a "not implemented" hint and no skills are written.

### Option B — Manual collection

Drop your own 50-skill pool into `${SKILLMUTATOR_DATA_ROOT}/skills/train-community-50/<skill-name>/SKILL.md`. The fine-tuning side (`skill-scanner-finetune/scripts/prepare_dataset.py`) only requires `SKILL.md` + accompanying scripts in any layout.

## License hygiene

Before redistributing or fine-tuning on a skill body, please check its license. The paper's training data is **not** redistributed for this reason — only the procedure that re-creates an equivalent dataset.

## Why two collections?

- The **evaluation** collection is fixed and public, so a third party can verify Table 1 / Table 2.
- The **training** collection is freely-substitutable; the fine-tuning result holds as long as the pool is roughly comparable in size, diversity of attack surface, and natural-language styles.
