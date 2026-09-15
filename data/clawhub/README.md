# ClawHub skill corpus — metadata only

The raw ClawHub skill artifacts (SKILL.md + scripts + references, ~1.3 GB
including all mutation trees; ~60 MB for the source skills alone) are
**third-party content and are not redistributed here**. This directory
provides identifying metadata only: skill name, owner, ClawHub URL,
version, and evaluation pool.

## Files

- `clawhub_skills.csv` — the **evaluation** corpus (in-the-wild + Finding 8), one row per skill.
- `train_community_skills.csv` — the **fine-tuning training host pool** (`pools = train_community`),
  same schema, one row per skill: the 68 community-authored ClawHub skills the SkillMutator pipeline
  mutates to build the distillation training corpus (distinct from the evaluation corpus above; see
  `artifact/code/skillmutator/docs/SKILLS_SETUP.md`). Bodies are not redistributed.

## Columns

| column | meaning |
|---|---|
| `pools` | evaluation pool(s) the skill belongs to (`;`-separated) |
| `slug` | ClawHub skill identifier (name) |
| `display_name` | human-readable name (from ClawHub listing) |
| `owner_id` | ClawHub owner/author id |
| `version` | evaluated version |
| `clawhub_url` | `https://clawhub.ai/skills/<slug>` |
| `api_url` | ClawHub API endpoint for the exact version |
| `license` | license declared on ClawHub (blank = none declared) |
| `downloads`, `stars` | ClawHub popularity signals at crawl time |
| `published_at_ms` | publish timestamp (epoch ms) |
| `summary` | one-line skill description |

## Pools

`clawhub_skills.csv` (evaluation, 296 skills):

| pool | n | role in paper |
|---|---|---|
| `clean_175` | 175 | stratified 175 clean pool (new round) |
| `clean_pool` | 200 | ClawHub-LLM benign candidate pool |
| `finding8_clean25` | 25 | 25 clean samples for Finding 8 |
| `finding8_susp100` | 100 | 100 suspicious for Finding 8 (4 strata) |

`train_community_skills.csv` (fine-tuning, separate file):

| pool | n | role in paper |
|---|---|---|
| `train_community` | 68 | community host skills mutated to build the distillation training corpus |

## Obtaining the raw artifacts

The original skill files can be re-downloaded from ClawHub via the
`api_url` column, or requested from the authors. If the ClawHub listing
is no longer available, contact the corresponding author at
**climbkim@kaist.ac.kr** for the crawled snapshot used in the paper.
