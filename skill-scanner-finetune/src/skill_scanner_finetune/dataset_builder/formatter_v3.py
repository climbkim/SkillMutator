"""Schema v3 formatter — renders `AnalysisResultV3` into an OpenAI JSONL entry.

Assistant content layout (no Verdict / Mitigation by design):

    ## Phase 1: Purpose Extraction
    ```json
    <phase1 json>
    ```

    ## Phase 2: Added-Scope Enumeration
    ```json
    <phase2 json>
    ```

    ## Phase 3: Principle Violations
    <phase3 markdown as-is>

    ## Phase 4: Category Mapping
    <phase4 markdown as-is>

Metadata: schema_version is set to "v3"; attack_category is normalized via
the taxonomy table in taxonomy.py. ground_truth / confidence /
impact_scope etc. are NOT extracted here — v3 has no Verdict block — those
metadata fields are carried from `mutation_metadata` when available and left
empty otherwise.
"""

from __future__ import annotations

import json
from typing import Any

from .taxonomy import normalize_attack_category

SYSTEM_CONTENT_V3 = (
    "You are an expert AI agent security analyst specializing in LLM-powered "
    "agent skill security. You analyze agent skills — composed of SKILL.md "
    "instruction documents and Python helper scripts — using a principle-first "
    "detection framework (schema v3). You reason step by step, cite specific "
    "file locations and exact quoted evidence, and treat the description "
    "field as an audit target rather than ground truth. Your final output "
    "must follow the exact 4-section layout (Phase 1 purpose, Phase 2 added "
    "scope, Phase 3 principle violations, Phase 4 category mapping)."
)


def _fmt_json_block(obj: Any) -> str:
    return "```json\n" + json.dumps(obj, ensure_ascii=False, indent=2) + "\n```"


def build_assistant_content_v3(phase_outputs: dict) -> str:
    p1 = phase_outputs.get("phase1", {}) or {}
    p2 = phase_outputs.get("phase2", {}) or {}
    p3 = phase_outputs.get("phase3", "") or ""
    p4 = phase_outputs.get("phase4", "") or ""

    parts = [
        "## Phase 1: Purpose Extraction",
        "",
        _fmt_json_block(p1),
        "",
        "## Phase 2: Added-Scope Enumeration",
        "",
        _fmt_json_block(p2),
        "",
        "## Phase 3: Principle Violations",
        "",
        p3.strip() if isinstance(p3, str) else _fmt_json_block(p3),
        "",
        "## Phase 4: Category Mapping",
        "",
        p4.strip() if isinstance(p4, str) else _fmt_json_block(p4),
        "",
    ]
    return "\n".join(parts)


def format_jsonl_entry_v3(
    analysis_result,
    skill_files_formatted: str,
    mutation_timestamp: str = "",
    mutation_iteration: int = 0,
    source_skill_dir: str = "",
    mutated_skill_dir: str = "",
    phase_outputs_path: str = "",
    token_count: int = 0,
    analysis_model: str = "",
    analysis_provider: str = "",
) -> dict:
    """Render `AnalysisResultV3` into an OpenAI JSONL entry."""
    assistant_content = build_assistant_content_v3(
        analysis_result.phase_outputs or {}
    )

    normalized_cat = normalize_attack_category(analysis_result.attack_category)

    # v3 has no Verdict block; carry metadata from mutation_metadata if present.
    mm = analysis_result.mutation_metadata or {}
    ground_truth = (
        "VULNERABLE" if analysis_result.is_malicious else "SAFE"
    )

    return {
        "messages": [
            {"role": "system", "content": SYSTEM_CONTENT_V3},
            {"role": "user",
             "content": f"Analyze this agent skill for security vulnerabilities:\n\n{skill_files_formatted}"},
            {"role": "assistant", "content": assistant_content},
        ],
        "metadata": {
            "schema_version":       "v3",
            "skill_name":           analysis_result.skill_name,
            "is_malicious":         analysis_result.is_malicious,
            "attack_category":      normalized_cat,
            "mutation_iteration":   mutation_iteration,
            "mutation_timestamp":   mutation_timestamp,
            "ground_truth":         ground_truth,
            "confidence":           mm.get("confidence", ""),
            "impact_scope":         mm.get("impact_scope", ""),
            "reversibility":        mm.get("reversibility", ""),
            "detection_difficulty": mm.get("detection_difficulty", ""),
            "source_skill_dir":     source_skill_dir,
            "mutated_skill_dir":    mutated_skill_dir,
            "phase_outputs_path":   phase_outputs_path,
            "token_count":          token_count,
            "analysis_model":       analysis_model,
            "analysis_provider":    analysis_provider,
            "split":                "",
        },
    }
