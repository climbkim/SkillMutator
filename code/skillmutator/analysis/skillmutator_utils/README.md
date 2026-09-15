# skillmutator_utils

Shared library for parsing, verdict computation, refusal classification, and
data-tree access used by both `Skillmutator-RQ1` and `Skillmutator-RQ2`.

The unified data tree (the `--data-root` produced by
`scripts/consolidate_to_datatree.py`, e.g. `./skillmutator-data/`) is the single
source of truth; all functions in this package read from it (no dependency on the
original scattered scanner outputs).

## Modules

| Module                | Purpose                                                |
|-----------------------|--------------------------------------------------------|
| `paths.py`            | Tree layout, oracle/mode/iter enumerations, cat-folder mapping |
| `parsers.py`          | Read raw `ss_report.md` / `snyk_report.md` / `judge_v2.json` |
| `verdicts.py`         | `ss_strict`, `snyk_lenient_identity`, `llm_v2`         |
| `classifications.py`  | Refusal classes (read from `meta.json` in tree)        |
| `filters.py`          | Per-iter eligibility, last_good_iter helper            |
| `data_access.py`      | Tree walker (`iter_scenarios`, `load_verdict`, `load_meta`) |
| `refusal.py`          | High-level: trajectories, summaries, valid_scenarios, rules |
| `_historical/`        | One-time data-tree builders (build_dataset, rejudge_missing) |

## Usage

```python
import sys; sys.path.insert(0, "path/to/skillmutator/analysis")  # dir that contains skillmutator_utils/
from skillmutator_utils import (
    aggregate_scenario_final,        # paper Table IV cells
    aggregate_per_iter,              # RQ2 trajectory (carry_forward / rule_1 / rule_2)
    refusal_summary,                 # refusal table
    valid_scenarios,                 # canonical denominator set
    build_trajectories,              # per-scenario classification trace
    iter_scenarios, load_verdict,    # tree walkers
)

# Paper Table 1 cell (gpt-5.4 self on gpt-5.4 dataset)
r = aggregate_scenario_final("gpt-5.4", "select", "llm/gpt-5.4-self")
# {"n": 76, "detected": 66, "rate_pct": 86.84}

# RQ2 iter trajectory (carry-forward, denom=last_good_from_iter_0)
rows = aggregate_per_iter("gpt-5.4", "select", "llm/gpt-5.4-self",
                          rule="carry_forward")
# [{"iter": 0, "n": 76, "detected": 70, ...}, ...]

# Refusal summary
refusal_summary("gpt-5.4", "no-select")
# {"total_scenarios": 221, "normal": 198, "silent_failure": 4, ...,
#  "any_refusal_rate_pct": 18.55}
```

## Verdict definitions (canonical)

These are the single source of truth for "what counts as detected" in both
RQ1 and RQ2 papers. To change a definition, edit `verdicts.py` only — every
analysis script will pick up the new behavior.

| Function                 | Criterion                                         |
|--------------------------|---------------------------------------------------|
| `ss_strict`              | `delta_total > 0` OR `delta_critical > 0`         |
| `snyk_lenient_identity`  | any new HIGH-severity finding identity in mutated |
| `llm_v2`                 | `judge_v2.json["detected"]`                       |

## Refusal handling rules

`refusal.py` exposes three rules, each with a different denominator policy:

| Rule              | Denominator           | iter K with refusal/missing handling          |
|-------------------|-----------------------|-----------------------------------------------|
| `rule_1`          | per-iter (varies)     | scenario excluded from K                      |
| `rule_2`          | fixed across iters    | counted as undetected (False)                 |
| `carry_forward`   | fixed across iters    | uses verdict at last_good_iter ≤ K (RQ2)      |

`carry_forward` is the canonical RQ2 rule: refusal at iter K means "no new
mutation produced", so the most recent successful iter's verdict persists.

## Denominator criteria

`valid_scenarios(oracle, mode, criterion=...)`:

| Criterion                  | Meaning                                                 |
|----------------------------|---------------------------------------------------------|
| `last_good_from_iter_0`    | iter_0 classification == normal (default; paper conv.)  |
| `all_attempted`            | every (skill, cat) seen in the tree                     |
| `refusal_clean`            | all iters [0..max] are normal                           |
| `any_normal_iter`          | at least one iter is normal                             |

## `_historical/`

Holds the one-time data-tree builder (`build_dataset.py`) and the missing-v2
filler (`rejudge_missing.py`). They depend on the original scattered scanner
outputs that have since been deleted, so they are not expected to run as-is.
Kept here for provenance / reproducibility documentation only.
