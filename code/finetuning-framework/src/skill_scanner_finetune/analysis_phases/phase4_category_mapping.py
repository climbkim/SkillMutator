"""Phase 4 — Category Mapping (schema v3).

Label-only layer: cross-references Phase 3 bullets to 13 categories +
Uncategorized. No evidence is re-emitted; each line is
    - [P<n>(, P<n>...)] <file>:<section>
"""

from __future__ import annotations

from .base_phase_v3 import BasePhaseV3, PhaseInputV3


CATEGORY_ORDER = [
    "Information Gathering",
    "Over-engineering",
    "Data Integrity Risks",
    "Advertising Injection",
    "False Attribution",
    "Code Quality Degradation",
    "Configuration Weakening",
    "Data Exfiltration",
    "Disruption & Interference",
    "Brand Hijacking",
    "Supply Chain Attack",
    "Persistence Control",
    "Privilege Escalation",
    "Uncategorized",
]


class Phase4CategoryMapping(BasePhaseV3):
    PHASE_ID = 4
    PHASE_NAME = "Category Mapping"
    PROMPT_FILE = "phase4_category_mapping"
    REQUIRED_PLACEHOLDERS = ("phase3_output",)
    OUTPUT_FORMAT = "markdown"

    def _prompt_context(self, inp: PhaseInputV3) -> dict:
        ctx = super()._prompt_context(inp)
        ctx["phase3_output"] = inp.prev_phases.get("phase3", "")
        return ctx

    def _parse_output(self, raw: str, inp: PhaseInputV3) -> str:
        return raw.strip()
