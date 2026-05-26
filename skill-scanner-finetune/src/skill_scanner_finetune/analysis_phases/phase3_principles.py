"""Phase 3 — Principle Violations (schema v3).

Output is Markdown with 9 fixed sections (P1..P9). Empty sections emit
`(none)`. For P9 bullets, a `[CWE-<num>]` tag is appended.
"""

from __future__ import annotations

import json

from .base_phase_v3 import BasePhaseV3, PhaseInputV3


PRINCIPLE_HEADERS = [
    "P1 Purpose-Action Alignment",
    "P2 Trust Boundary Integrity",
    "P3 Consent & Transparency",
    "P4 Scope Containment",
    "P5 Reciprocity",
    "P6 Hidden Conditionality",
    "P7 Framing Dissonance",
    "P8 Representation Fidelity",
    "P9 Safe Composition",
]


class Phase3Principles(BasePhaseV3):
    PHASE_ID = 3
    PHASE_NAME = "Principle Violations"
    PROMPT_FILE = "phase3_principles"
    REQUIRED_PLACEHOLDERS = (
        "phase1_output", "phase2_output", "skill_files_formatted",
    )
    OUTPUT_FORMAT = "markdown"

    def _prompt_context(self, inp: PhaseInputV3) -> dict:
        ctx = super()._prompt_context(inp)
        ctx["phase1_output"] = json.dumps(
            inp.prev_phases.get("phase1", {}), ensure_ascii=False, indent=2,
        )
        ctx["phase2_output"] = json.dumps(
            inp.prev_phases.get("phase2", {}), ensure_ascii=False, indent=2,
        )
        return ctx

    def _parse_output(self, raw: str, inp: PhaseInputV3) -> str:
        # keep raw markdown; downstream validator checks section presence
        return raw.strip()
