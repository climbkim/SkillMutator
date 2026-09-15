"""Schema v3 base — prompt-file-aware phase class.

Design notes:
- System prompt and per-phase user prompts are loaded from
  `analysis_phases/prompts/*.md` at import time; file contents are treated
  as format-string templates (`{placeholder}`).
- Phases declare their expected placeholders; missing context raises early.
- Phase 3/4 outputs are Markdown (not JSON). `_parse_output` keeps raw text.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
import json
import re


PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(name: str) -> str:
    p = PROMPTS_DIR / f"{name}.md"
    if not p.is_file():
        raise FileNotFoundError(f"prompt missing: {p}")
    return p.read_text(encoding="utf-8")


SYSTEM_PROMPT = load_prompt("system")


@dataclass
class PhaseInputV3:
    skill_name: str
    skill_dir: Path
    skill_files_formatted: str
    is_malicious: bool
    attack_category: str | None
    mutation_metadata: dict = field(default_factory=dict)
    prev_phases: dict = field(default_factory=dict)


class BasePhaseV3(ABC):
    PHASE_ID: int
    PHASE_NAME: str
    PROMPT_FILE: str                         # e.g. "phase1_purpose"
    REQUIRED_PLACEHOLDERS: tuple[str, ...] = ()
    OUTPUT_FORMAT: str = "json"              # "json" | "markdown"

    def __init__(self, llm):
        self.llm = llm
        self._template = load_prompt(self.PROMPT_FILE)

    # ----- public API -----
    def run(self, inp: PhaseInputV3) -> dict | str:
        prompt = self._build_prompt(inp)
        raw = self.llm.chat([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ])
        return self._parse_output(raw, inp)

    # ----- overridable -----
    def _build_prompt(self, inp: PhaseInputV3) -> str:
        """Substitute only registered placeholders. Leaves stray `{...}` in the
        prompt (e.g., code examples, evidence quotes containing brace literals)
        intact — unlike `str.format`, which treats every `{...}` as a key.
        """
        ctx = self._prompt_context(inp)
        missing = [k for k in self.REQUIRED_PLACEHOLDERS if k not in ctx]
        if missing:
            raise KeyError(f"{self.PROMPT_FILE}: missing placeholders {missing}")
        text = self._template
        for name, value in ctx.items():
            text = text.replace("{" + name + "}", str(value))
        return text

    def _prompt_context(self, inp: PhaseInputV3) -> dict:
        """Return mapping of placeholder name -> value. Override per-phase."""
        return {
            "skill_name":            inp.skill_name,
            "skill_dir":             str(inp.skill_dir),
            "skill_files_formatted": inp.skill_files_formatted,
        }

    def _parse_output(self, raw: str, inp: PhaseInputV3) -> dict | str:
        if self.OUTPUT_FORMAT == "json":
            return self._extract_json(raw)
        return raw.strip()

    # ----- helpers -----
    def _extract_json(self, raw: str) -> dict | list:
        m = re.search(r"```(?:json)?\s*([\s\S]+?)```", raw, re.IGNORECASE)
        text = m.group(1).strip() if m else raw.strip()
        start = min(
            (text.find("{") if "{" in text else len(text)),
            (text.find("[") if "[" in text else len(text)),
        )
        if start < len(text):
            text = text[start:]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}
