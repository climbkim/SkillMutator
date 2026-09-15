"""Anthropic-published-skills backend for the community-skill crawler.

`crawl(target_count, output_dir)` shallow-clones github.com/anthropics/skills and
copies the 17 evaluation skills used in the paper into `<output_dir>/<name>/`.
Skills are located by searching the clone for a `<name>/SKILL.md` (robust to the
repo's directory layout). `target_count` caps how many of the 17 are copied
(<= 0 or unset = all 17).

These skills are Anthropic's; they are cloned from the public repository, not
redistributed here. See docs/SKILLS_SETUP.md.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_REPO = "https://github.com/anthropics/skills.git"

# The 17 evaluation skills (paper eval set); see docs/SKILLS_SETUP.md.
EVAL_17 = [
    "algorithmic-art", "brand-guidelines", "canvas-design", "claude-api",
    "doc-coauthoring", "docx", "frontend-design", "internal-comms",
    "mcp-builder", "pdf", "pptx", "skill-creator", "slack-gif-creator",
    "theme-factory", "web-artifacts-builder", "webapp-testing", "xlsx",
]


def _locate(root: Path, name: str) -> Path | None:
    """Find a directory named `name` that contains a SKILL.md, anywhere in root."""
    for skill_md in root.rglob("SKILL.md"):
        if skill_md.parent.name == name:
            return skill_md.parent
    return None


def crawl(target_count: int, output_dir: str) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    names = EVAL_17[:target_count] if (target_count and target_count > 0) else EVAL_17

    with tempfile.TemporaryDirectory() as td:
        print(f"[anthropic] cloning {_REPO} (shallow) ...")
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", _REPO, td],
                check=True, stdout=sys.stdout, stderr=sys.stderr,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"[anthropic] git clone failed ({e}); is git installed and the "
                  f"network reachable?", file=sys.stderr)
            return

        copied = missing = 0
        for name in names:
            src = _locate(Path(td), name)
            if src is None:
                print(f"[anthropic] skill not found in repo: {name}", file=sys.stderr)
                missing += 1
                continue
            dst = out / name
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            copied += 1
            print(f"[anthropic] {copied:>3}. {name} -> {dst}")

    print(f"[anthropic] done: copied {copied} skill(s) to {out} ({missing} not found).")
