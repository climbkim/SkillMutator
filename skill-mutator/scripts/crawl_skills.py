"""crawl_skills.py -- community-skill crawler entry point.

This is the user-facing entry point referenced in `docs/SKILLS_SETUP.md` and by
`run.sh --crawl`. It dispatches to `skill_mutator.crawler.<registry>` and calls
its `crawl(target_count, output_dir)` function.

Bundled backends:
  --registry anthropic : clone github.com/anthropics/skills and copy the 17
                         published evaluation skills used in the paper.
  --registry clawhub   : read a ClawHub manifest CSV (e.g. the artifact's
                         artifact/data/clawhub/clawhub_skills.csv, or
                         $SKILLMUTATOR_CLAWHUB_CSV) and fetch each skill's
                         SKILL.md from the public ClawHub API (sha256-verified).
No skill bodies are redistributed; the backends re-fetch from the public
sources. Add `src/skill_mutator/crawler/<registry>.py` with a
`crawl(target_count, output_dir)` function to support another source.

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
from pathlib import Path

# Make the `skill_mutator` package importable when run as a plain script
# (scripts/crawl_skills.py) so `skill_mutator.crawler.<registry>` resolves.
_SRC = Path(__file__).resolve().parent.parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


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