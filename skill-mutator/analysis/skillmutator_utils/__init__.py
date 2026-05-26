"""Skillmutator-utils — shared parsers, verdict definitions, classification logic,
and data-tree access helpers for the Skillmutator-RQ1 and Skillmutator-RQ2
analyses. The unified data lives at ${SKILLMUTATOR_DATA_ROOT}/.

Conventions:
- Verdicts are computed from raw scanner reports via the canonical criteria
  documented in `verdicts.py`. Each scenario × iter × scanner has a verdict.json
  cached in the data tree.
- Refusal classification is per (oracle, mode, skill, cat, iter); scenarios with
  iter_0 != 'normal' are typically excluded as "no real attack" (denominator
  filter).
"""
from .parsers   import parse_ss_report, parse_snyk_report, parse_judge_v2, parse_mutation_meta, extract_scan_section
from .verdicts  import ss_strict, snyk_lenient_identity, llm_v2
from .classifications import classify_entry, load_classifications
from .paths     import data_root, scenario_dir, scanner_dir
from .filters   import iter_0_normal_scenarios, last_good_iter, is_iter_normal
from .data_access import iter_scenarios, load_verdict, load_meta, scanner_keys_for
from .refusal import (
    build_trajectories, refusal_summary, per_iter_classification_counts,
    valid_scenarios, rule1_eligible, rule2_verdict,
    aggregate_per_iter, aggregate_scenario_final,
)
from .judge import (
    judge_call, judge_scanner_output,
    JUDGE_MODEL, JUDGE_SYSTEM, JUDGE_USER_TEMPLATE,
)
