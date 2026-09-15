"""populate_verdicts.py — bridge a single mutation run's scan results into the
canonical data tree as per-scanner verdict.json cells.

The mutation pipeline writes per-cell scan reports and a
`comparison_<skill>.csv` (with ss_detected / snyk_detected / llm_detected), but
the analysis builders read `<cell>/<scanner>/verdict.json`. This script converts
the former into the latter so `run.sh` can chain mutate -> scan -> consolidate ->
populate -> build without the full author-side data tree.

Usage:
    python scripts/populate_verdicts.py \
        --comparison-csv demo-results/comparison_sample_skill.csv \
        --oracle gpt-4o-mini --mode select \
        --data-root demo-data --scanner-model gpt-4o-mini
"""
from __future__ import annotations
import argparse, csv, json, os, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "analysis"))
from skillmutator_utils.paths import CAT_FOLDER_FROM_LABEL  # noqa: E402


def _to_bool(v: str) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--comparison-csv", required=True)
    ap.add_argument("--oracle", required=True)
    ap.add_argument("--mode", default="select")
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--scanner-model", required=True,
                    help="LLM-scanner model used (its self-scanner cell is llm/<model>-self)")
    args = ap.parse_args()

    data_root = Path(args.data_root)
    self_scanner = f"llm/{args.scanner_model}-self"
    written = 0
    with open(args.comparison_csv, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            skill = row.get("skill_name", "").strip()
            label = row.get("attack_category", "").strip()
            cat = CAT_FOLDER_FROM_LABEL.get(label, label.lower().replace(" ", "_"))
            it = int(row.get("mutation_iteration", 0) or 0)
            cell = data_root / args.oracle / args.mode / skill / cat / f"iter_{it}"
            # A comparison-CSV row means a real mutation was produced -> "normal".
            # classify_all() reads meta.json["classification"]; consolidate does not
            # write it, so set it here (proper fix: emit it from consolidate_to_datatree).
            meta_p = cell / "meta.json"
            if meta_p.is_file():
                try:
                    meta = json.loads(meta_p.read_text(encoding="utf-8"))
                except Exception:
                    meta = {}
                meta.setdefault("classification", "normal")
                meta_p.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            cells = {
                "ss":   _to_bool(row.get("ss_detected", "")),
                "snyk": _to_bool(row.get("snyk_detected", "")) if _to_bool(row.get("snyk_available", "")) else False,
                self_scanner: _to_bool(row.get("llm_detected", "")),
            }
            for subpath, detected in cells.items():
                out = cell / subpath / "verdict.json"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps({"detected": detected}), encoding="utf-8")
                written += 1
    print(f"[populate_verdicts] wrote {written} verdict.json cells under {data_root}/{args.oracle}/{args.mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
