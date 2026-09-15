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


# ===========================================================================
# Corpus builder — teacher-driven training-data generation ([A] data-gen step)
# ===========================================================================
# `build_corpus` is the high-level orchestrator that prepare_dataset.py drives:
# it walks a skill collection, runs the schema-v3 four-phase analysis pipeline
# with a *teacher* model on each skill, and renders every result into a JSONL
# training example via `format_jsonl_entry_v3`. The teacher defaults to the
# inexpensive gpt-4o-mini and is overridable (prepare_dataset `--teacher`).

_MUT_META_SIDECAR = "mutation_metadata.json"


class _OpenAITeacher:
    """Minimal OpenAI-compatible chat client used as the distillation teacher.

    Exposes the `.chat(messages) -> str` / `.model_name` interface expected by
    the schema-v3 phases (`SecurityAnalysisPipelineV3`). Reads OPENAI_API_KEY
    (and optionally OPENAI_BASE_URL) from the environment.
    """

    def __init__(self, model_name: str = "gpt-4o-mini", provider: str = "openai",
                 temperature: float = 0.2):
        self.model_name = model_name
        self.provider = provider
        self.temperature = temperature
        from openai import OpenAI  # lazy import; keeps --help usable without deps
        import os
        kwargs = {}
        if os.getenv("OPENAI_BASE_URL"):
            kwargs["base_url"] = os.environ["OPENAI_BASE_URL"]
        self._client = OpenAI(**kwargs)

    def chat(self, messages: list[dict]) -> str:
        resp = self._client.chat.completions.create(
            model=self.model_name, messages=messages, temperature=self.temperature,
        )
        return resp.choices[0].message.content or ""


def _discover_skill_items(skills_dir, iters):
    """Discover the (skill, is_malicious, category, iteration) items to distill.

    Label resolution per skill (a directory containing a top-level SKILL.md):
      1. `mutation_metadata.json` sidecar next to SKILL.md — authoritative
         (is_malicious / attack_category / impact_scope / reversibility /
          detection_difficulty / confidence / mutation_iteration).
      2. else, paper mutation-tree path `.../generate_skill/<cat>/iter_<n>/...`
         — malicious, category=<cat>, iteration=<n>.
      3. else — benign (is_malicious=False, attack_category="NONE", iter 0).

    `iters` (a set or None) filters malicious items by iteration.
    """
    import json as _json
    from pathlib import Path as _P

    root = _P(skills_dir)
    items = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        sdir = skill_md.parent
        is_mal, cat, itr, meta = False, "NONE", 0, {}

        # rule 2 (path) first, so a sidecar can still override it below
        parts = sdir.parts
        if "generate_skill" in parts:
            gi = parts.index("generate_skill")
            if gi + 1 < len(parts):
                cat = parts[gi + 1]
            for p in parts:
                if p.startswith("iter_"):
                    try:
                        itr = int(p.split("_", 1)[1])
                    except ValueError:
                        pass
            is_mal = True

        # rule 1 (sidecar) — authoritative
        side = sdir / _MUT_META_SIDECAR
        if side.is_file():
            try:
                meta = _json.loads(side.read_text(encoding="utf-8"))
            except Exception:
                meta = {}
            if meta.get("attack_category"):
                cat = meta["attack_category"]
            is_mal = bool(meta.get("is_malicious",
                                   cat not in (None, "", "NONE")))
            if "mutation_iteration" in meta:
                try:
                    itr = int(meta["mutation_iteration"])
                except (TypeError, ValueError):
                    pass

        if not is_mal:
            cat = "NONE"
        if is_mal and iters is not None and itr not in iters:
            continue
        items.append({"skill_dir": sdir, "is_malicious": is_mal,
                      "attack_category": cat, "iteration": itr, "metadata": meta})
    return items


def build_corpus(skills_dir, teacher_model: str = "gpt-4o-mini",
                 iters=(0, 1, 2), output_path=None, provider: str = "openai"):
    """Walk `skills_dir`, distill each skill with the teacher, write JSONL.

    Args:
        skills_dir:    root of the skill collection (one SKILL.md per skill dir).
        teacher_model: teacher model id (default gpt-4o-mini; overridable).
        iters:         iterations to include for mutation-tree skills.
        output_path:   JSONL file to write (one training example per line).
        provider:      teacher provider label (default "openai").

    Returns the output path. Requires OPENAI_API_KEY at call time.
    """
    import json as _json
    from pathlib import Path as _P
    from ..analysis_phases.pipeline_v3 import SecurityAnalysisPipelineV3
    from ..utils.file_reader import read_folder, format_files_for_llm

    output_path = _P(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    itset = set(iters) if iters else None
    items = _discover_skill_items(skills_dir, itset)
    if not items:
        raise SystemExit(f"[build_corpus] no SKILL.md found under {skills_dir}")

    llm = _OpenAITeacher(model_name=teacher_model, provider=provider)
    pipeline = SecurityAnalysisPipelineV3(llm)

    n = 0
    with output_path.open("w", encoding="utf-8") as fh:
        for it in items:
            sdir = it["skill_dir"]
            files = read_folder(sdir, recursive=True, max_file_size_kb=200)
            formatted = format_files_for_llm(files, include_tree=True,
                                             max_total_chars=80_000)
            result = pipeline.analyze(
                skill_dir=sdir,
                skill_files_formatted=formatted,
                is_malicious=it["is_malicious"],
                attack_category=(None if it["attack_category"] == "NONE"
                                 else it["attack_category"]),
                mutation_metadata=it["metadata"],
            )
            entry = format_jsonl_entry_v3(
                result, formatted,
                mutation_iteration=it["iteration"],
                source_skill_dir=str(sdir),
                mutated_skill_dir=str(sdir) if it["is_malicious"] else "",
                analysis_model=teacher_model,
                analysis_provider=provider,
            )
            fh.write(_json.dumps(entry, ensure_ascii=False) + "\n")
            n += 1
            tag = f"malicious:{it['attack_category']}" if it["is_malicious"] else "benign"
            print(f"  [{n}/{len(items)}] {result.skill_name} ({tag})")

    print(f"[build_corpus] wrote {n} example(s) -> {output_path}")
    return output_path
