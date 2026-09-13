"""Community-skill crawler backends.

`scripts/crawl_skills.py` (and `run.sh --crawl --registry <name>`) dispatches to
`skill_mutator.crawler.<name>`, calling its `crawl(target_count, output_dir)`.

Bundled backends:
  - ``anthropic`` : clone github.com/anthropics/skills and copy the 17 published
                    evaluation skills used in the paper.
  - ``clawhub``   : read a ClawHub manifest CSV and fetch each skill's SKILL.md
                    from the public ClawHub API (integrity-checked via sha256).

No skill bodies are redistributed in this repo; these backends re-fetch them
from their public sources. Add a new ``<registry>.py`` with a
``crawl(target_count, output_dir)`` function to support another source.
"""
