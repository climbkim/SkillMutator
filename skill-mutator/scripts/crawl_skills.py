"""crawl_skills.py -- placeholder community-skill crawler.

The crawler scaffolding lives in `src/skill_mutator/crawler/`; this script is
the user-facing entry point referenced in `docs/SKILLS_SETUP.md`. The actual
selectors will vary per registry (ClawHub, GitHub topic searches, etc.); edit
the crawler module before running on a new source.

Usage:
    python scripts/crawl_skills.py \\
        --registry clawhub \\
        --target-count 50 \\
        --output-dir ./data/train-community-50
"""
from __future__ import annotations

import argparse
import importlib
import sys


def main() -> int:
    ap = argparse.ArgumentParser(description="Crawl community-authored skills for the training pool.")
    ap.add_argument("--registry", default="clawhub",
                    help="Registry name; resolved as `skill_mutator.crawler.<registry>`.")
    ap.add_argument("--target-count", type=int, default=50,
                    help="Stop after this many successful skills are saved.")
    ap.add_argument("--output-dir", required=True,
                    help="Where to write per-skill subdirectories.")
    args = ap.parse_args()

    try:
        mod = importlib.import_module(f"skill_mutator.crawler.{args.registry}")
    except ImportError as e:
        print(f"[error] crawler '{args.registry}' not implemented: {e}", file=sys.stderr)
        print("[hint] add a new module under src/skill_mutator/crawler/ "
              "with a `crawl(target_count, output_dir)` function.", file=sys.stderr)
        return 2

    crawl_fn = getattr(mod, "crawl", None)
    if crawl_fn is None:
        print(f"[error] {args.registry}.crawl(...) not defined.", file=sys.stderr)
        return 2

    crawl_fn(target_count=args.target_count, output_dir=args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())