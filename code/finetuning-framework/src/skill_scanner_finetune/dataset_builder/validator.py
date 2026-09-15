"""Dataset format validation — schema, token counts, label distribution."""

from __future__ import annotations

import json
from pathlib import Path

VALID_GROUND_TRUTHS = {"VULNERABLE", "SAFE"}
VALID_IMPACT_SCOPES = {"LOCAL", "SYSTEM", "REMOTE"}
VALID_REVERSIBILITY = {"REVERSIBLE", "IRREVERSIBLE"}
VALID_DETECTION_DIFFICULTY = {"Low", "Medium", "High"}
VALID_ATTACK_CATEGORIES = {
    "Information Gathering", "Privilege Escalation", "Persistence Control",
    "Data Exfiltration", "Disruption & Interference", "Supply Chain Attack",
    "Configuration Weakening", "Data Integrity Risks", "Code Quality Degradation",
    "Advertising Injection", "Brand Hijacking", "False Attribution",
    "Over-engineering", "NONE",
}
REQUIRED_METADATA_FIELDS = [
    "skill_name", "is_malicious", "attack_category", "mutation_iteration",
    "ground_truth", "confidence", "impact_scope", "reversibility",
    "detection_difficulty", "mutation_timestamp", "source_skill_dir",
    "token_count", "analysis_model", "analysis_provider", "split",
]
MAX_TOKEN_WARN = 8_192   # advisory: anything above this is a WARNING
MAX_TOKEN_HARD = 32_768  # hard limit: max allowed for fine-tuning


class DatasetValidator:

    def validate_entry(self, entry: dict) -> list[str]:
        """Validate a single entry. Returns a list of error messages ([] = valid)."""
        errors: list[str] = []

        # 1. messages structure
        msgs = entry.get("messages", [])
        if len(msgs) != 3:
            errors.append(f"messages count error: expected 3, got {len(msgs)}")
        else:
            roles = [m.get("role") for m in msgs]
            if roles != ["system", "user", "assistant"]:
                errors.append(f"messages role order error: {roles}")

        # 2. content is non-empty
        for i, msg in enumerate(msgs):
            if not msg.get("content", "").strip():
                errors.append(f"messages[{i}] content is empty")

        # 3. required metadata fields
        meta = entry.get("metadata", {})
        for field in REQUIRED_METADATA_FIELDS:
            if field not in meta:
                errors.append(f"missing required metadata field: {field}")

        # 4. enum validation
        if meta.get("ground_truth") not in VALID_GROUND_TRUTHS:
            errors.append(f"ground_truth value error: {meta.get('ground_truth')}")
        if meta.get("impact_scope") not in VALID_IMPACT_SCOPES:
            errors.append(f"impact_scope value error: {meta.get('impact_scope')}")
        if meta.get("reversibility") not in VALID_REVERSIBILITY:
            errors.append(f"reversibility value error: {meta.get('reversibility')}")
        if meta.get("detection_difficulty") not in VALID_DETECTION_DIFFICULTY:
            errors.append(f"detection_difficulty value error: {meta.get('detection_difficulty')}")
        if meta.get("attack_category") not in VALID_ATTACK_CATEGORIES:
            errors.append(f"attack_category value error: {meta.get('attack_category')}")

        # 5. confidence range
        conf = meta.get("confidence", -1)
        if not isinstance(conf, (int, float)) or not (0.0 <= conf <= 1.0):
            errors.append(f"confidence out of range: {conf}")

        # 6. Label consistency is intentionally NOT an error: an original
        #    (un-mutated) skill may carry a real vulnerability, so
        #    is_malicious=False + ground_truth=VULNERABLE is permitted.

        # 7. token count
        token_count = meta.get("token_count", 0)
        if token_count > MAX_TOKEN_HARD:
            errors.append(f"token count exceeds hard limit: {token_count} > {MAX_TOKEN_HARD}")
        elif token_count > MAX_TOKEN_WARN:
            errors.append(f"[WARNING] token count exceeds advisory limit: {token_count} > {MAX_TOKEN_WARN}")

        # 8. assistant content format check. Under the 4-Phase v3 schema the
        #    final section is "## Phase 4: Category Mapping", so its presence
        #    is the structural check.
        if len(msgs) > 2:
            assistant_content = msgs[2].get("content", "")
            if "## Phase 4" not in assistant_content:
                errors.append("assistant content is missing the '## Phase 4' header")

        return errors

    def validate_dataset(self, jsonl_path: Path) -> dict:
        """Validate a whole dataset. Returns a report dict."""
        lines = [l for l in jsonl_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        entries = []
        for i, line in enumerate(lines):
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as e:
                entries.append({"_parse_error": str(e), "_line": i})

        all_errors: dict[int, list[str]] = {}
        label_counts: dict = {}
        attack_cat_counts: dict = {}
        token_counts: list[int] = []
        skill_names: set = set()

        for i, entry in enumerate(entries):
            if "_parse_error" in entry:
                all_errors[i] = [f"JSON parse error: {entry['_parse_error']}"]
                continue
            errs = self.validate_entry(entry)
            if errs:
                all_errors[i] = errs
            meta = entry.get("metadata", {})
            gt = meta.get("ground_truth", "UNKNOWN")
            label_counts[gt] = label_counts.get(gt, 0) + 1
            cat = meta.get("attack_category", "UNKNOWN")
            attack_cat_counts[cat] = attack_cat_counts.get(cat, 0) + 1
            tc = meta.get("token_count", 0)
            token_counts.append(tc)
            skill_names.add(meta.get("skill_name", ""))

        # Duplicate detection
        seen: set = set()
        duplicates: list = []
        for i, entry in enumerate(entries):
            if "_parse_error" in entry:
                continue
            meta = entry.get("metadata", {})
            key = (meta.get("skill_name"), meta.get("attack_category"), meta.get("mutation_iteration"))
            if key in seen:
                duplicates.append((i, key))
            seen.add(key)

        total = len(entries)
        safe_count = label_counts.get("SAFE", 0)
        vuln_count = label_counts.get("VULNERABLE", 0)
        warning_count = sum(
            1 for errs in all_errors.values() if all(e.startswith("[WARNING]") for e in errs)
        )
        error_count = len(all_errors) - warning_count  # real errors only (excludes WARNING)

        return {
            "total_entries": total,
            "valid_entries": total - error_count - warning_count,
            "error_entries": error_count,
            "warning_entries": warning_count,
            "errors": {k: v for k, v in all_errors.items() if not all(e.startswith("[WARNING]") for e in v)},
            "warnings": {k: v for k, v in all_errors.items() if all(e.startswith("[WARNING]") for e in v)},
            "label_distribution": label_counts,
            "safe_ratio": safe_count / total if total else 0,
            "attack_category_distribution": attack_cat_counts,
            "skill_count": len(skill_names),
            "token_stats": {
                "min": min(token_counts) if token_counts else 0,
                "max": max(token_counts) if token_counts else 0,
                "mean": round(sum(token_counts) / len(token_counts), 1) if token_counts else 0,
                "over_8192": sum(1 for t in token_counts if t > MAX_TOKEN_WARN),
            },
            "duplicates": duplicates,
            "passed": error_count == 0 and len(duplicates) == 0,  # WARNINGs do not affect pass/fail
        }

    def validate_and_report(self, jsonl_path: Path, report_path: Path | None = None) -> bool:
        """Run validation and print a report. Returns whether it passed."""
        report = self.validate_dataset(jsonl_path)

        print(f"\n{'='*60}")
        print(f"Dataset Validation Report: {jsonl_path.name}")
        print(f"{'='*60}")
        print(f"Total entries    : {report['total_entries']}")
        print(f"Valid entries    : {report['valid_entries']}")
        print(f"Error entries    : {report['error_entries']}")
        print(f"Skill count      : {report['skill_count']}")
        print(f"Label distribution: {report['label_distribution']}")
        print(f"SAFE ratio       : {report['safe_ratio']:.1%}")
        print(f"Token stats      : {report['token_stats']}")
        print(f"Duplicates       : {len(report['duplicates'])}")
        print(f"PASSED           : {'PASS' if report['passed'] else 'FAIL'}")

        if report["errors"]:
            print("\nErrors (first 10):")
            for i, (idx, errs) in enumerate(list(report["errors"].items())[:10]):
                print(f"  Entry {idx}: {errs}")

        if report_path:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"\nReport saved: {report_path}")

        return report["passed"]


def validate(jsonl_path) -> list[str]:
    """Structural validation used by prepare_dataset.py ([2/3] step).

    Returns a list of "line N: <error>" strings ([] = all valid). Checks the
    three-turn system/user/assistant messages structure, non-empty content, and
    that the assistant turn carries the four schema-v3 phase headers. Optional
    metadata enums are intentionally NOT enforced here: benign (SAFE) entries
    legitimately leave impact_scope / reversibility / detection_difficulty empty.
    Use `DatasetValidator` directly for the stricter per-field enum checks.
    """
    import json as _json
    from pathlib import Path as _P

    errors: list[str] = []
    for i, line in enumerate(_P(jsonl_path).read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            entry = _json.loads(line)
        except Exception as ex:  # noqa: BLE001
            errors.append(f"line {i}: invalid JSON ({ex})")
            continue
        msgs = entry.get("messages", [])
        if [m.get("role") for m in msgs] != ["system", "user", "assistant"]:
            errors.append(f"line {i}: messages roles != system/user/assistant")
            continue
        if any(not (m.get("content") or "").strip() for m in msgs):
            errors.append(f"line {i}: empty message content")
        assistant = msgs[2].get("content", "")
        for header in ("## Phase 1", "## Phase 2", "## Phase 3", "## Phase 4"):
            if header not in assistant:
                errors.append(f"line {i}: assistant missing '{header}'")
                break
    return errors
