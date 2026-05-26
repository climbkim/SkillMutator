"""Compute IER detection-rate dynamics in three variants.

For each oracle (gpt-4o-mini, gpt-5.4-mini, gpt-5.4) in select mode,
walks all (skill, category, iter) combinations and computes the
detection rate per scanner (ss, snyk, llm-self) per iteration.

Outputs (under OUT_DIR):
  ier_dynamics.csv       — raw per-iter (excludes scenarios without scan)
  ier_dynamics_pinA.csv  — Option A: raw for iter 0-3; iter 4 = cross_matrix
                           (Table III) hardcoded re-pinned values
  ier_dynamics_pinD.csv  — Option D: every iter forward-filled per scenario
                           (re-pin to latest scan ≤ current iter)
  ier_dynamics_summary.txt — sanity check pivot view
"""
import csv
import json
import os
from pathlib import Path

# Data tree: env var SKILLMUTATOR_DATA_ROOT (see evaluate/README.md).
_ROOT_ENV = os.environ.get("SKILLMUTATOR_DATA_ROOT")
if not _ROOT_ENV:
    raise SystemExit("SKILLMUTATOR_DATA_ROOT not set. Export it to your data tree.")
ROOT = Path(_ROOT_ENV)

OUT_DIR = Path(__file__).resolve().parents[2] / "outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_CSV_RAW   = OUT_DIR / "ier_dynamics.csv"
OUT_CSV_PINA  = OUT_DIR / "ier_dynamics_pinA.csv"
OUT_CSV_PIND  = OUT_DIR / "ier_dynamics_pinD.csv"
OUT_TXT = OUT_DIR / "ier_dynamics_summary.txt"

ORACLES = ["gpt-4o-mini", "gpt-5.4-mini", "gpt-5.4"]

LLM_SELF = {
    "gpt-4o-mini": "gpt-4o-mini-self",
    "gpt-5.4-mini": "gpt-5.4-mini-self",
    "gpt-5.4": "gpt-5.4-self",
}

ITERS = [0, 1, 2, 3, 4]
SCANNERS = ["ss", "snyk", "llm"]

# Paper-canonical re-pinned final values from Table III (tab:cross_matrix).
# Used as iter_4 override in pinA.
CROSS_MATRIX = {
    "gpt-4o-mini":  {"ss": (2.08, 48),  "snyk": (16.67, 48), "llm": (35.42, 48)},
    "gpt-5.4-mini": {"ss": (6.35, 63),  "snyk": (9.52, 63),  "llm": (71.43, 63)},
    "gpt-5.4":      {"ss": (7.89, 76),  "snyk": (9.21, 76),  "llm": (86.84, 76)},
}


def read_detected(verdict_path):
    if not verdict_path.exists():
        return None
    try:
        with verdict_path.open(encoding="utf-8") as f:
            obj = json.load(f)
        return bool(obj.get("detected"))
    except Exception:
        return None


def read_classification(meta_path):
    """Return classification string ('normal' = refusal-free, else refusal type)."""
    if not meta_path.exists():
        return None
    try:
        with meta_path.open(encoding="utf-8") as f:
            obj = json.load(f)
        return obj.get("classification")
    except Exception:
        return None


def collect_oracle(oracle):
    """Return list of dicts: one per (skill, cat, iter) with detection per scanner."""
    base = ROOT / oracle / "select"
    llm_self = LLM_SELF[oracle]
    rows = []
    if not base.exists():
        return rows
    for skill_dir in sorted(base.iterdir()):
        if not skill_dir.is_dir():
            continue
        for cat_dir in sorted(skill_dir.iterdir()):
            if not cat_dir.is_dir():
                continue
            for it in ITERS:
                iter_dir = cat_dir / f"iter_{it}"
                if not iter_dir.exists():
                    continue
                ss_det = read_detected(iter_dir / "ss" / "verdict.json")
                snyk_det = read_detected(iter_dir / "snyk" / "verdict.json")
                llm_det = read_detected(iter_dir / "llm" / llm_self / "verdict.json")
                classification = read_classification(iter_dir / "meta.json")
                rows.append({
                    "oracle": oracle,
                    "skill": skill_dir.name,
                    "category": cat_dir.name,
                    "iter": it,
                    "ss": ss_det,
                    "snyk": snyk_det,
                    "llm": llm_det,
                    "classification": classification,
                })
    return rows


def aggregate_raw(all_rows):
    """Per (oracle, iter, scanner) counts using raw (skip None) per iter."""
    agg = {}
    for r in all_rows:
        for sc in SCANNERS:
            v = r[sc]
            if v is None:
                continue
            key = (r["oracle"], r["iter"], sc)
            d = agg.setdefault(key, {"n": 0, "det": 0})
            d["n"] += 1
            if v:
                d["det"] += 1
    return agg


def aggregate_pinD(all_rows):
    """Paper-canonical re-pin: for each scenario at iter k, use the LATEST iter
    j <= k where classification == 'normal' (refusal-free). Otherwise exclude.
    """
    # Index by (oracle, skill, cat) -> iter -> {ss, snyk, llm, classification}
    by_scenario = {}
    for r in all_rows:
        key = (r["oracle"], r["skill"], r["category"])
        by_scenario.setdefault(key, {})[r["iter"]] = r

    # For each scenario, find latest-refusal-free iter <= k for each iter k.
    pinned = {}  # (oracle, skill, cat) -> {iter -> {ss, snyk, llm} from latest normal iter}
    for key, iter_map in by_scenario.items():
        pinned[key] = {}
        last_normal_iter = None
        for it in ITERS:
            entry = iter_map.get(it)
            if entry is not None and entry.get("classification") == "normal":
                last_normal_iter = it
            if last_normal_iter is not None:
                src = iter_map[last_normal_iter]
                pinned[key][it] = {sc: src.get(sc) for sc in SCANNERS}
            # else: leave undefined (scenario has no refusal-free iter <= k)

    # Aggregate
    agg = {}
    for (oracle, _, _), iter_map in pinned.items():
        for it, sc_map in iter_map.items():
            for sc, v in sc_map.items():
                if v is None:
                    continue
                k = (oracle, it, sc)
                d = agg.setdefault(k, {"n": 0, "det": 0})
                d["n"] += 1
                if v:
                    d["det"] += 1
    return agg


def aggregate_pinA(raw_agg):
    """Replace iter_4 values with cross_matrix Table III hardcoded rates."""
    new_agg = dict(raw_agg)
    for oracle, sc_map in CROSS_MATRIX.items():
        for sc, (rate_pct, n) in sc_map.items():
            det = round(rate_pct * n / 100)
            new_agg[(oracle, 4, sc)] = {"n": n, "det": det}
    return new_agg


def write_csv(path, agg):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["oracle", "iter", "scanner", "n", "detected", "rate_pct"])
        for (oracle, it, sc), d in sorted(agg.items()):
            rate = 100.0 * d["det"] / d["n"] if d["n"] else 0.0
            w.writerow([oracle, it, sc, d["n"], d["det"], f"{rate:.2f}"])
    print(f"wrote {path}")


def write_summary(agg_raw, agg_pinA, agg_pinD):
    lines = ["IER detection-rate dynamics (select mode).",
             "Scanners: ss = skill-security-scan, snyk = Snyk Agent Scan, llm = self LLM scanner.",
             ""]

    def pivot(title, agg):
        lines.append(f"=== {title} ===")
        for oracle in ORACLES:
            lines.append(f"--- {oracle} (select) ---")
            lines.append(f"{'scanner':<6} | {'i0':>6} {'i1':>6} {'i2':>6} {'i3':>6} {'i4':>6}")
            for sc in SCANNERS:
                cells = []
                for it in ITERS:
                    d = agg.get((oracle, it, sc))
                    cells.append(f"{(100.0 * d['det'] / d['n']):>5.1f}%" if d and d['n'] else "  -  ")
                lines.append(f"{sc:<6} | " + " ".join(cells))
            lines.append("")
        lines.append("")

    pivot("RAW per-iter rates", agg_raw)
    pivot("Option A — iter 4 re-pinned to cross_matrix (Table III)", agg_pinA)
    pivot("Option D — full forward-fill re-pin per scenario", agg_pinD)

    OUT_TXT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT_TXT}")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_rows = []
    for oracle in ORACLES:
        all_rows.extend(collect_oracle(oracle))

    agg_raw = aggregate_raw(all_rows)
    agg_pinD = aggregate_pinD(all_rows)
    agg_pinA = aggregate_pinA(agg_raw)

    write_csv(OUT_CSV_RAW, agg_raw)
    write_csv(OUT_CSV_PINA, agg_pinA)
    write_csv(OUT_CSV_PIND, agg_pinD)
    write_summary(agg_raw, agg_pinA, agg_pinD)


if __name__ == "__main__":
    main()
