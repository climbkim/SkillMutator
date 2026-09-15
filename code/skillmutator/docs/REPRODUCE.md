# Reproducing the paper

This document walks through reproducing **Table IV** (cross-scanner detection-rate matrix), **Table III** (safety-refusal summary), **Table V** (select vs no-select), and **Figure 4** (IER dynamics) from the paper. The fine-tuned-scanner floats (Tables VI/X/XI, Figures 5–6) are reproduced from the sister repository `skill-scanner-finetune` (bundled here as `../finetuning-framework/`).

## What you need

| Resource | Purpose | Approx. cost / time |
|----------|---------|---------------------|
| OpenAI API access (GPT-4o-mini, GPT-5.4-mini, GPT-5.4) | Three adversarial oracles + GPT-5.4 judge | ≈ $200 for full benchmark |
| Snyk account (optional) | Snyk Agent Scan baseline | Free tier sufficient |
| 50 + 17 community/Anthropic skills | Mutation source pool | See [SKILLS_SETUP.md](SKILLS_SETUP.md) |
| ~60 GB disk | Mutated SKILL.md tree + scan reports + judge verdicts | — |
| 1 GPU (optional) | Required only if you also reproduce RQ3 (fine-tuning side) | — |

## End-to-end reproduction

### 0. Environment

```bash
pip install -e .[all]
cp .env.example .env
# Edit .env: OPENAI_API_KEY, ANTHROPIC_API_KEY (optional), SNYK_TOKEN (optional), HF_TOKEN
export SKILLMUTATOR_DATA_ROOT=$PWD/data/skillmutator-data   # tree to be created below
```

### 1. Collect skills

Follow [SKILLS_SETUP.md](SKILLS_SETUP.md) to assemble:

- **17 Anthropic-published skills** for evaluation.
- **30 community-authored skills** (initial crawl) plus **20 additional crawled skills** for the training pool used by the sister fine-tuning repo.

Skills should land at `${SKILLMUTATOR_DATA_ROOT}/skills/<skill-name>/SKILL.md` (and accompanying scripts).

### 2. Run the SkillMutator pipeline against each oracle

For each adversarial oracle in `{gpt-4o-mini, gpt-5.4-mini, gpt-5.4}`:

```bash
python scripts/run_all_skills.py \
    --skills-dir ${SKILLMUTATOR_DATA_ROOT}/skills/eval-anthropic-17 \
    --provider openai --model <oracle> \
    --mode select --max-iters 5 \
    --result-dir ${SKILLMUTATOR_DATA_ROOT}/<oracle>/select
```

This produces, per (skill, attack-category, iter): an injected `SKILL.md`, an `injected_content.md` ground-truth note, and a `meta.json` with the per-iter classification (normal / silent_failure / explicit_refusal / partial_refusal).

### 3. Run all five scanners on the mutated tree

For each oracle's mutated tree:

```bash
# Rule-based / commercial
python scripts/run_test_scanner.py --scanner skill-security --root ${SKILLMUTATOR_DATA_ROOT}/<oracle>/select
python scripts/run_test_scanner.py --scanner snyk          --root ${SKILLMUTATOR_DATA_ROOT}/<oracle>/select

# LLM scanners (one pass per scanner model)
for sc in gpt-4o-mini gpt-5.4-mini gpt-5.4; do
    python scripts/run_test_scanner.py --scanner llm --provider openai --model "$sc" \
           --root ${SKILLMUTATOR_DATA_ROOT}/<oracle>/select
done
```

Verdicts are adjudicated by a single GPT-5.4 judge (see `analysis/skillmutator_utils/judge.py`) and written into the data tree as `verdict.json` per scanner cell.

### 4. Build the paper tables

```bash
mkdir -p analysis/rq1/scripts/outputs analysis/rq2/scripts/outputs

python analysis/rq1/scripts/build_tab1_cross_matrix.py
python analysis/rq1/scripts/build_tab2_refusal_summary.py
python analysis/rq2/scripts/build_tab_iter_trajectory.py
python analysis/rq2/scripts/plot_iter_trajectory.py
```

Outputs land in each script's adjacent `outputs/` directory: `tab1_cross_matrix.{csv,tex}`, `tab2_refusal_summary.csv`, `tab_iter_trajectory.{csv,csv-per-oracle}`, and `fig_iter_trajectory.{pdf,png}`.

## Validation

Against `${SKILLMUTATOR_DATA_ROOT}` you should observe (within ±2 detected scenarios due to LLM-judge stochasticity):

| Cell                                  | Expected detection rate |
|---------------------------------------|-------------------------|
| `skill-security-scan` × GPT-5.4 ds    | ~ 7.9 %                 |
| Snyk Agent Scan × GPT-5.4 ds          | ~ 9.2 %                 |
| GPT-4o-mini scanner × GPT-5.4 ds      | ~ 23.7 %                |
| GPT-5.4-mini scanner × GPT-5.4 ds     | ~ 79.0 %                |
| GPT-5.4 scanner × GPT-5.4 ds (self)   | ~ 86.8 %                |

A larger drift suggests judge-stochasticity bias; rerun the judge cells with `analysis/skillmutator_utils/judge.py` to converge.

## Caveats

- **n = 51 / 63 / 76** scenarios survive per oracle after the published-iter pin-and-recover procedure described in §Experimental Setup of the paper.
- The 4-Phase distilled scanner result (paper §RQ3 Finding 1) is reproduced from the sister repo, not here.
- The GPT-5.4-mini cross-cell on the GPT-5.4 dataset is sensitive to two distinct workflows:
  - test_scanner_result-based fill (single pass at last_good_iter): ~ 80 %
  - per-iter rescan + last_good_iter aggregation: ~ 90 %

  The paper reports the test_scanner_result-based number for consistency.
