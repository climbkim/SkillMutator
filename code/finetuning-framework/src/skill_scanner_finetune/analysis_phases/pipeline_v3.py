"""Schema v3 — 4-phase analysis pipeline.

Sequence:
    Phase 1 Purpose Extraction        (JSON)
    Phase 2 Added-Scope Enumeration   (JSON)
    Phase 3 Principle Violations      (Markdown, 9 sections)
    Phase 4 Category Mapping          (Markdown, 14 sections; label-only)

Phase 4 is terminal. There is no Verdict / Mitigation block.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from .base_phase_v3 import PhaseInputV3
from .phase1_purpose import Phase1Purpose
from .phase2_added_scope import Phase2AddedScope
from .phase3_principles import Phase3Principles
from .phase4_category_mapping import Phase4CategoryMapping

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResultV3:
    skill_name: str
    is_malicious: bool
    attack_category: str | None
    mutation_metadata: dict
    phase_outputs: dict = field(default_factory=dict)  # phase1/phase2 JSON, phase3/phase4 str
    analysis_model: str = ""
    analysis_provider: str = ""
    schema_version: str = "v3"


class SecurityAnalysisPipelineV3:
    def __init__(self, llm):
        self.model_name = getattr(llm, "model_name", "unknown")
        self.provider = llm.__class__.__name__.lower().replace("llm", "")
        self.phases = [
            Phase1Purpose(llm),
            Phase2AddedScope(llm),
            Phase3Principles(llm),
            Phase4CategoryMapping(llm),
        ]

    def analyze(
        self,
        skill_dir: Path,
        skill_files_formatted: str,
        is_malicious: bool,
        attack_category: str | None = None,
        mutation_metadata: dict | None = None,
        skill_name: str | None = None,
    ) -> AnalysisResultV3:
        # caller may override; otherwise derive from path. Mutation layout is
        # experiments/<exp>/mutations/<skill>/<ts>/generate_skill/<cat>/iter_<n>/skills
        # so we pick the segment right after "mutations". Fall back to the
        # dir name for non-mutation paths (e.g., baseline `skills/<name>`).
        if skill_name is None:
            parts = skill_dir.parts
            if "mutations" in parts:
                idx = parts.index("mutations")
                if idx + 1 < len(parts):
                    skill_name = parts[idx + 1]
            if skill_name is None:
                skill_name = (
                    skill_dir.parent.name if skill_dir.name == "skills"
                    else skill_dir.name
                )
        mutation_metadata = mutation_metadata or {}
        phase_outputs: dict = {}

        for phase in self.phases:
            logger.info(f"[{skill_name}] Phase {phase.PHASE_ID}: {phase.PHASE_NAME}")
            inp = PhaseInputV3(
                skill_name=skill_name,
                skill_dir=skill_dir,
                skill_files_formatted=skill_files_formatted,
                is_malicious=is_malicious,
                attack_category=attack_category,
                mutation_metadata=mutation_metadata,
                prev_phases=dict(phase_outputs),
            )
            try:
                out = phase.run(inp)
            except Exception as e:
                logger.error(f"[{skill_name}] Phase {phase.PHASE_ID} error: {e}")
                out = {"error": str(e)} if phase.OUTPUT_FORMAT == "json" else f"(error: {e})"
            phase_outputs[f"phase{phase.PHASE_ID}"] = out

        return AnalysisResultV3(
            skill_name=skill_name,
            is_malicious=is_malicious,
            attack_category=attack_category,
            mutation_metadata=mutation_metadata,
            phase_outputs=phase_outputs,
            analysis_model=self.model_name,
            analysis_provider=self.provider,
        )

    def save_result(self, result: AnalysisResultV3, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "schema_version":    result.schema_version,
            "skill_name":        result.skill_name,
            "is_malicious":      result.is_malicious,
            "attack_category":   result.attack_category,
            "mutation_metadata": result.mutation_metadata,
            "phase_outputs":     result.phase_outputs,
            "analysis_model":    result.analysis_model,
            "analysis_provider": result.analysis_provider,
        }
        output_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info(f"Analysis v3 saved: {output_path}")
