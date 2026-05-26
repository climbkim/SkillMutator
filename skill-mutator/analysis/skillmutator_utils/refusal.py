"""refusal.py — high-level helpers for refusal-aware analysis.

Builds per-scenario trajectories from raw mutation JSONs, computes refusal
summaries (the table in RQ1's refusal_summary.csv), and applies the two
denominator-handling rules used by the paper:

  Rule 1 (per-iter): at iter K, only count scenarios where classification[K]
                     == 'normal'. Refusals at K are excluded from that iter's
                     denominator. Used for iter-trajectory plots where each
                     iter is measured independently.

  Rule 2 (fixed denom): denominator is the set of "valid" scenarios (default:
                        iter_0 == 'normal'). At any iter K, refusal / missing
                        is counted as undetected (False). Used for fair
                        comparison against a fixed scenario set.
"""
from collections import Counter, defaultdict
from typing import Optional

from .classifications import classify_all
from .data_access import iter_scenarios, list_iters, load_verdict
from .paths import MAX_ITER_BY_MODE


# ---------------------------------------------------------------------------
# Trajectories + summaries
# ---------------------------------------------------------------------------

def build_trajectories(oracle: str, mode: str) -> dict[tuple[str, str], dict]:
    """Per (skill, cat_folder) → {
        'classifications': {iter: cls},
        'final_iter': int,
        'final_classification': str,
        'any_refusal': bool,
        'trajectory': '/-joined human-readable trace',
      }
    """
    cls_map = classify_all(oracle, mode)
    by_scen: dict[tuple[str, str], dict[int, str]] = defaultdict(dict)
    for (sk, cat, it), c in cls_map.items():
        by_scen[(sk, cat)][it] = c
    out = {}
    for (sk, cat), iters in by_scen.items():
        max_it = max(iters)
        final_cls = iters[max_it]
        any_ref = any(c != "normal" for c in iters.values())
        traj = " / ".join(f"i{k}:{iters[k]}" for k in sorted(iters))
        out[(sk, cat)] = {
            "classifications": dict(iters),
            "final_iter": max_it,
            "final_classification": final_cls,
            "any_refusal": any_ref,
            "trajectory": traj,
        }
    return out


def refusal_summary(oracle: str, mode: str) -> dict:
    """Aggregate refusal counts per oracle/mode at scenario-final granularity.

    Returns a dict matching RQ1's refusal_summary.csv schema:
      total_scenarios, normal, explicit_refusal, silent_failure,
      partial_refusal, any_refusal, any_refusal_rate_pct
    """
    trajs = build_trajectories(oracle, mode)
    total = len(trajs)
    final_counts = Counter(t["final_classification"] for t in trajs.values())
    any_ref = sum(1 for t in trajs.values() if t["any_refusal"])
    return {
        "oracle": oracle,
        "mode": mode,
        "total_scenarios": total,
        "normal":           final_counts.get("normal", 0),
        "explicit_refusal": final_counts.get("explicit_refusal", 0),
        "silent_failure":   final_counts.get("silent_failure", 0),
        "partial_refusal":  final_counts.get("partial_refusal", 0),
        "any_refusal":           any_ref,
        "any_refusal_rate_pct": round(any_ref / total * 100, 2) if total else 0.0,
    }


def per_iter_classification_counts(oracle: str, mode: str) -> dict:
    """Per-iter histogram of classifications. Returns {iter: Counter}."""
    cls_map = classify_all(oracle, mode)
    out = defaultdict(Counter)
    for (sk, cat, it), c in cls_map.items():
        out[it][c] += 1
    return {k: dict(v) for k, v in sorted(out.items())}


# ---------------------------------------------------------------------------
# Denominator filters
# ---------------------------------------------------------------------------

def valid_scenarios(oracle: str, mode: str, *, criterion: str = "last_good_from_iter_0") -> set[tuple[str, str]]:
    """Return the canonical denominator set for an analysis.

    criterion ∈ {
        'last_good_from_iter_0' (default): scenarios where iter_0 produced a
            real (non-refusal) mutation. These are scenarios with a defined
            evaluation point at every iter K via carry-forward from
            last_good_iter (= iter_0 when later iters refuse).
            **Naming note**: the original (confusing) name 'iter_0_normal'
            referred to *experiments* iter_0, NOT the dataset's iter_0.
            (The dataset's published iter_0 SKILL.md is actually the recovered
            last_good_iter from experiments.)
            Yields paper conventions: 215 noselect, 76 select gpt-5.4,
            63 gpt-5.4-mini, 47 gpt-4o-mini.
        'all_attempted'  : every (skill, cat) found in experiments
                           (silent failures included; 51/63/76 select, 221 noselect)
        'refusal_clean'  : every iter [0..max] is normal (strictest)
        'any_normal_iter': at least one iter is normal
    }
    """
    cls_map = classify_all(oracle, mode)
    all_scen = {(sk, cat) for (sk, cat, _) in cls_map}
    max_iter = MAX_ITER_BY_MODE[mode]
    if criterion == "all_attempted":
        return all_scen
    if criterion in ("last_good_from_iter_0", "iter_0_normal"):  # alias for legacy
        return {(sk, cat) for (sk, cat) in all_scen
                if cls_map.get((sk, cat, 0)) == "normal"}
    if criterion == "refusal_clean":
        return {(sk, cat) for (sk, cat) in all_scen
                if all(cls_map.get((sk, cat, it)) == "normal" for it in range(max_iter + 1))}
    if criterion == "any_normal_iter":
        return {(sk, cat) for (sk, cat) in all_scen
                if any(cls_map.get((sk, cat, it)) == "normal" for it in range(max_iter + 1))}
    raise ValueError(f"unknown criterion: {criterion}")


# ---------------------------------------------------------------------------
# Rule 1 / Rule 2 verdict adjustments
# ---------------------------------------------------------------------------

def rule1_eligible(cls_map: dict, sk: str, cat: str, it: int) -> bool:
    """Rule 1: scenario contributes to iter K denominator iff classification[K] == 'normal'."""
    return cls_map.get((sk, cat, it)) == "normal"


def rule2_verdict(cls_map: dict, sk: str, cat: str, it: int, verdict: Optional[bool]) -> bool:
    """Rule 2: denom is fixed; refusal at iter K → undetected (False),
    missing scan → undetected (False).

    Returns True only if classification[K] == 'normal' AND verdict is True."""
    if cls_map.get((sk, cat, it)) != "normal":
        return False
    return bool(verdict) if verdict is not None else False


# ---------------------------------------------------------------------------
# High-level aggregations
# ---------------------------------------------------------------------------

def aggregate_per_iter(oracle: str, mode: str, scanner_subpath: str, *,
                       rule: str = "carry_forward",
                       denom: str = "last_good_from_iter_0") -> list[dict]:
    """Compute per-iter detection rate using the specified rule + denominator.

    Returns rows: [{iter, n, detected, normal_undet, carried_forward, rate_pct}, ...]

    rule ∈ {
        'carry_forward' (default, paper's RQ2 approach): denom is fixed; at
            iter K, each scenario uses the verdict at last_good_iter ≤ K.
            If iter K is refusal/missing, the previous successful iter's
            verdict carries forward. n is the same across all K.
        'rule_2': denom fixed; refusal/missing → undetected (False).
        'rule_1': per-iter denom; scenarios with refusal at K excluded from K.
    }
    """
    cls_map = classify_all(oracle, mode)
    if rule == "rule_1":
        scen_set = {(sk, cat) for (sk, cat, _) in cls_map}
    else:
        scen_set = valid_scenarios(oracle, mode, criterion=denom)
    rows = []
    max_iter = MAX_ITER_BY_MODE[mode]
    for it in range(max_iter + 1):
        det = nd = ref_or_miss = carried = 0
        if rule == "rule_1":
            iter_scen = {(sk, cat) for (sk, cat) in scen_set
                         if rule1_eligible(cls_map, sk, cat, it)}
            n = len(iter_scen)
            for (sk, cat) in iter_scen:
                v = load_verdict(oracle, mode, sk, cat, it, scanner_subpath)
                if v is True: det += 1
                else: nd += 1
        elif rule == "rule_2":
            n = len(scen_set)
            for (sk, cat) in scen_set:
                v = load_verdict(oracle, mode, sk, cat, it, scanner_subpath)
                cls = cls_map.get((sk, cat, it))
                if cls == "normal" and v is True:
                    det += 1
                elif cls == "normal" and v is False:
                    nd += 1
                else:
                    ref_or_miss += 1
        else:  # carry_forward
            n = len(scen_set)
            for (sk, cat) in scen_set:
                # find last_good_iter ≤ it
                lg = None
                for k in range(it + 1):
                    if cls_map.get((sk, cat, k)) == "normal":
                        lg = k
                if lg is None: continue
                if lg != it: carried += 1
                v = load_verdict(oracle, mode, sk, cat, lg, scanner_subpath)
                if v is True: det += 1
                else: nd += 1
        rate = det / n * 100 if n else 0.0
        rows.append({
            "iter": it, "n": n, "detected": det,
            "normal_undet": nd, "refusal_or_missing": ref_or_miss,
            "carried_forward": carried,
            "rate_pct": round(rate, 2),
        })
    return rows


def aggregate_scenario_final(oracle: str, mode: str, scanner_subpath: str, *,
                             denom: str = "last_good_from_iter_0",
                             max_iter_cap: Optional[int] = None) -> dict:
    """Compute a single scenario-final detection rate. The verdict per scenario
    is taken at last_good_iter (= highest iter ≤ max_iter_cap with class=='normal').

    Returns: {n, detected, rate_pct}.
    """
    cls_map = classify_all(oracle, mode)
    scen_set = valid_scenarios(oracle, mode, criterion=denom)
    cap = max_iter_cap if max_iter_cap is not None else MAX_ITER_BY_MODE[mode]
    det = 0; n = len(scen_set)
    for (sk, cat) in scen_set:
        lg = None
        for it in range(cap + 1):
            if cls_map.get((sk, cat, it)) == "normal":
                lg = it
        if lg is None: continue
        v = load_verdict(oracle, mode, sk, cat, lg, scanner_subpath)
        if v is True: det += 1
    return {"n": n, "detected": det, "rate_pct": round(det / n * 100, 2) if n else 0.0}
