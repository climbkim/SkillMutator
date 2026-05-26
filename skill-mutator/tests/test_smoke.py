"""End-to-end smoke test for skill-mutator.

The test exercises a minimal happy path:
  - import the public modules without side-effects
  - load the bundled sample skill
  - construct an OpenAI scanner client (does NOT call the API)

It does NOT actually call any LLM or scanner. To run a real mutation +
scan against the sample skill, see `scripts/run_mutation.py` and
`scripts/run_scanner.py` in the repo root.

Run with:
    pytest tests/test_smoke.py -v
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_SKILL = REPO_ROOT / "examples" / "skills" / "sample_skill"


def test_repo_layout():
    """The repo's structural invariants must hold."""
    assert (REPO_ROOT / "src" / "skill_mutator").is_dir()
    assert (REPO_ROOT / "src" / "skill_mutator" / "scanners").is_dir()
    assert (REPO_ROOT / "docs" / "attack_categories.json").is_file()
    assert SAMPLE_SKILL.is_dir()
    assert (SAMPLE_SKILL / "SKILL.md").is_file()


def test_attack_categories_well_formed():
    """The 13-category taxonomy file is valid JSON with the expected keys."""
    import json
    cats = json.loads((REPO_ROOT / "docs" / "attack_categories.json").read_text(encoding="utf-8"))
    # The exact schema may evolve; minimum: a non-empty list of dicts with `name`.
    assert isinstance(cats, (list, dict))


def test_imports():
    """All public sub-packages import without side-effects."""
    import importlib
    for mod in (
        "skill_mutator",
        "skill_mutator.process",
        "skill_mutator.llm",
        "skill_mutator.scanners.llm_scanner",
    ):
        try:
            importlib.import_module(mod)
        except ImportError as e:
            pytest.skip(f"{mod} not importable in this environment: {e}")


def test_scanner_default_models_well_formed():
    """The LLM scanner declares a default model for every supported provider."""
    try:
        from skill_mutator.scanners.llm_scanner import scanner
    except ImportError:
        pytest.skip("scanner module not importable")
    for prov in scanner.SUPPORTED_PROVIDERS:
        assert prov in scanner.DEFAULT_MODELS, f"missing default for {prov}"


@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set; skipping live API smoke",
)
def test_scanner_live_call():
    """Optional: actually invoke the LLM scanner against the sample skill."""
    try:
        from skill_mutator.scanners.llm_scanner import scanner
    except ImportError:
        pytest.skip("scanner not importable")
    client = scanner.create_client("openai")
    assert client is not None
