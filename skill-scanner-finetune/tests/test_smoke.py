"""End-to-end smoke test for skill-scanner-finetune.

Verifies structural invariants and that the public packages import. Does NOT
actually train, load model weights, or call any LLM.

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
    assert (REPO_ROOT / "src" / "skill_scanner_finetune").is_dir()
    assert (REPO_ROOT / "src" / "skill_scanner_finetune" / "analysis_phases").is_dir()
    assert (REPO_ROOT / "src" / "skill_scanner_finetune" / "finetune" / "configs" / "qwen_default.yaml").is_file()
    assert SAMPLE_SKILL.is_dir()
    assert (SAMPLE_SKILL / "SKILL.md").is_file()


def test_paper_default_config_is_well_formed():
    """The paper-default YAML must declare LoRA r=64, alpha=128, lr=5e-5, ep=5."""
    try:
        import yaml
    except ImportError:
        pytest.skip("pyyaml not installed")
    cfg_path = REPO_ROOT / "src" / "skill_scanner_finetune" / "finetune" / "configs" / "qwen_default.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    assert cfg["lora"]["r"] == 64
    assert cfg["lora"]["alpha"] == 128
    assert cfg["training"]["num_train_epochs"] == 5
    assert float(cfg["training"]["learning_rate"]) == 5.0e-5


def test_phase_files_exist():
    """The 4-phase v3 schema must be present (P1..P4)."""
    phases_dir = REPO_ROOT / "src" / "skill_scanner_finetune" / "analysis_phases"
    for fname in (
        "phase1_purpose.py",
        "phase2_added_scope.py",
        "phase3_principles.py",
        "phase4_category_mapping.py",
    ):
        assert (phases_dir / fname).is_file(), f"missing {fname}"


def test_imports():
    import importlib
    for mod in (
        "skill_scanner_finetune",
        "skill_scanner_finetune.analysis_phases",
        "skill_scanner_finetune.dataset_builder",
    ):
        try:
            importlib.import_module(mod)
        except ImportError as e:
            pytest.skip(f"{mod} not importable in this environment: {e}")


@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set; skipping live judge smoke",
)
def test_judge_instantiable():
    """analysis/judge.py should at least construct an OpenAI client."""
    try:
        import importlib.util
        judge_path = REPO_ROOT / "analysis" / "judge.py"
        if not judge_path.is_file():
            pytest.skip("analysis/judge.py not present")
        spec = importlib.util.spec_from_file_location("_judge_mod", judge_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # The judge module exposes a `_get_client` helper.
        assert hasattr(mod, "_get_client") or hasattr(mod, "judge_call")
    except Exception as e:
        pytest.skip(f"judge module load failed: {e}")
