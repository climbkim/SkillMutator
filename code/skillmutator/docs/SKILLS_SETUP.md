# Setting up the skill collections

This repo ships **no** skills (other than one tiny smoke-test sample at `examples/skills/sample_skill/`). Reproducing the paper requires assembling two disjoint collections yourself:

1. **17 evaluation skills** — Anthropic's officially published Agent Skills (mutation hosts for the benchmark).
2. **68 training skills** — community-authored skills from public registries (mutation hosts for the fine-tuning corpus); the exact pool is manifested in `artifact/data/clawhub/train_community_skills.csv`.

The strict separation ensures no train/test contamination.

> Not covered here: the **200 in-the-wild ClawHub skills** used for the Table VII
> wild evaluation (`claim05`) are scanned *unmutated*, so they are not a mutation
> host collection — see `artifact/data/clawhub/clawhub_skills.csv` (pools
> `clean_pool`/`clean_175`/`finding8_*`).

## 1. Anthropic-published skills (n = 17)

These are released by Anthropic for Claude. The bundled `anthropic` crawler
backend clones the official repo and copies the 17 paper skills for you:

```bash
# via run.sh (populates ./skills, then mutates the pool):
./run.sh --crawl 17 --registry anthropic --skills-dir ./skills
# or directly:
python scripts/crawl_skills.py --registry anthropic --target-count 17 \
       --output-dir ${SKILLMUTATOR_DATA_ROOT}/skills/eval-anthropic-17
```

Equivalently, by hand:

```bash
mkdir -p ${SKILLMUTATOR_DATA_ROOT}/skills/eval-anthropic-17
git clone https://github.com/anthropics/skills.git /tmp/anthropic-skills
for s in algorithmic-art brand-guidelines canvas-design claude-api \
         doc-coauthoring docx frontend-design internal-comms \
         mcp-builder pdf pptx skill-creator slack-gif-creator \
         theme-factory web-artifacts-builder webapp-testing xlsx; do
    cp -r "/tmp/anthropic-skills/$s" "${SKILLMUTATOR_DATA_ROOT}/skills/eval-anthropic-17/"
done
```

Verify each skill has at least a `SKILL.md` plus zero or more `.py` / template files. License: see Anthropic's repository (typically Apache 2.0 or MIT, but check per skill).

## 2. Community-authored training skills (n = 68)

These were collected from public skill registries (e.g. ClawHub, GitHub topic searches, community Discord shares). The repo ships the crawler **entry point** (`scripts/crawl_skills.py`) and a **ClawHub backend**, but **not** the skill bodies — licenses vary per skill.

To assemble your own pool of community skills, you can either:

### Option A — Use the included ClawHub crawler

```bash
# via run.sh (populates ./skills, then mutates the pool):
./run.sh --crawl 68 --registry clawhub --skills-dir ./skills
# or directly:
python scripts/crawl_skills.py --registry clawhub --target-count 68 \
       --output-dir ${SKILLMUTATOR_DATA_ROOT}/skills/train-community-68
```

`crawl_skills.py` dispatches to `skill_mutator.crawler.<registry>`. The bundled
`clawhub` backend reads a ClawHub manifest CSV — the artifact ships one at
`artifact/data/clawhub/clawhub_skills.csv`; elsewhere set `$SKILLMUTATOR_CLAWHUB_CSV`
to point at one (optionally filter with `$SKILLMUTATOR_CLAWHUB_POOL`, e.g.
`clean_175`). For each selected skill it fetches `SKILL.md` from the public
ClawHub API (verified against the manifest sha256) and writes a
`_clawhub_manifest.json` provenance sidecar (full file list + sha256). Only
`SKILL.md` is re-fetchable from the public API; full skill bodies are on request.
To add another registry, drop `src/skill_mutator/crawler/<registry>.py` with a
`crawl(target_count, output_dir)` function.

### Option B — Manual collection

Drop your own 68-skill pool into `${SKILLMUTATOR_DATA_ROOT}/skills/train-community-68/<skill-name>/SKILL.md`. The fine-tuning side (`skill-scanner-finetune/scripts/prepare_dataset.py`) only requires `SKILL.md` + accompanying scripts in any layout.

## License hygiene

Before redistributing or fine-tuning on a skill body, please check its license. The paper's training data is **not** redistributed for this reason — only the procedure that re-creates an equivalent dataset.

## Why two collections?

- The **evaluation** collection is fixed and public, so a third party can verify Table 1 / Table 2.
- The **training** collection is freely-substitutable; the fine-tuning result holds as long as the pool is roughly comparable in size, diversity of attack surface, and natural-language styles.
