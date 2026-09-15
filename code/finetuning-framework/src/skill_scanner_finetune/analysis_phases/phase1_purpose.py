"""Phase 1 — Purpose Extraction (schema v3).

Treats `description` as audit target (not ground truth):
  - Step A: probe description against 13 categories + 9 principles.
  - Step B: fallback chain for minimal_purpose
            (description -> frontmatter.name -> directory_name).
  - Step C: emit 5-axis allowlist.
  - Step D: flag purpose_anomalies.
"""

from __future__ import annotations

from .base_phase_v3 import BasePhaseV3, PhaseInputV3


_DEFAULT_OUTPUT = {
    "declared_purpose":       "",
    "minimal_purpose":        "",
    "purpose_source":         "directory_name",
    "description_malicious":  False,
    "description_probe_hits": [],
    "purpose_anomalies":      [],
    "allowlist_actions": {
        "filesystem":     [],
        "network":        [],
        "state":          [],
        "commands":       [],
        "permissions":    [],
        "output_content": [],
    },
    "declared_io_boundaries": "",
}


class Phase1Purpose(BasePhaseV3):
    PHASE_ID = 1
    PHASE_NAME = "Purpose Extraction"
    PROMPT_FILE = "phase1_purpose"
    REQUIRED_PLACEHOLDERS = ("skill_name", "skill_dir", "skill_files_formatted")
    OUTPUT_FORMAT = "json"

    def _parse_output(self, raw: str, inp: PhaseInputV3) -> dict:
        data = self._extract_json(raw)
        if not isinstance(data, dict) or not data:
            return dict(_DEFAULT_OUTPUT)
        # shallow-fill defaults so downstream code does not KeyError
        merged = dict(_DEFAULT_OUTPUT)
        merged.update(data)
        for k, v in _DEFAULT_OUTPUT["allowlist_actions"].items():
            merged.setdefault("allowlist_actions", {}).setdefault(k, v)
        return merged
