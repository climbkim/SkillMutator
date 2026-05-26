"""Phase 2 — Added-Scope Enumeration (schema v3).

Collects two kinds of units:
  - scope_expansion   : exceeds Phase 1 allowlist (5 axes)
  - unsafe_composition: within allowlist but matches a P9 danger pattern
"""

from __future__ import annotations

import json

from .base_phase_v3 import BasePhaseV3, PhaseInputV3


class Phase2AddedScope(BasePhaseV3):
    PHASE_ID = 2
    PHASE_NAME = "Added-Scope Enumeration"
    PROMPT_FILE = "phase2_added_scope"
    REQUIRED_PLACEHOLDERS = ("phase1_output", "skill_files_formatted")
    OUTPUT_FORMAT = "json"

    def _prompt_context(self, inp: PhaseInputV3) -> dict:
        ctx = super()._prompt_context(inp)
        ctx["phase1_output"] = json.dumps(
            inp.prev_phases.get("phase1", {}), ensure_ascii=False, indent=2
        )
        return ctx

    def _parse_output(self, raw: str, inp: PhaseInputV3) -> dict:
        data = self._extract_json(raw)
        if not isinstance(data, dict) or "added_units" not in data:
            return {"added_units": []}
        # Normalize path separators: always forward slashes. Model may emit
        # backslashes despite prompt guidance (Windows-influenced pathing).
        for u in data.get("added_units") or []:
            if isinstance(u, dict) and isinstance(u.get("file"), str):
                u["file"] = u["file"].replace("\\", "/")
        return data
