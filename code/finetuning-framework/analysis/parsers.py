"""parsers.py — read raw scanner reports and structured outputs.

Each parser returns a small dict (or None on failure) with the fields needed by
verdicts.py. Parsers do NOT compute verdicts themselves — they only extract.
"""
import json, re
from pathlib import Path
from typing import Optional


_SUMMARY_ROW = re.compile(r"\|\s*([A-Za-z][A-Za-z ]*?)\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*([+-]?\d+)\s*\|")


def parse_ss_report(md: Path) -> Optional[dict]:
    """Parse an ss_report.md and return the summary-table deltas.

    Returns dict with keys: delta_total, delta_critical, delta_score,
    baseline_total, baseline_critical, mutated_total, mutated_critical, raw.
    Returns None if file is missing or unparseable.
    """
    if not md.is_file(): return None
    text = md.read_text(encoding="utf-8", errors="replace")
    deltas = {row.lower().strip(): int(d) for row, d in _SUMMARY_ROW.findall(text)}
    if not deltas: return None
    out = {
        "delta_total":    deltas.get("total", 0),
        "delta_critical": deltas.get("critical", 0),
        "delta_warning":  deltas.get("warning", 0),
        "raw_md":         str(md),
    }
    # also try delta_score (Risk Score row has float)
    m = re.search(r"\|\s*Risk Score\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*\+?([+-]?[\d.]+)\s*\|", text)
    if m:
        try: out["delta_score"] = float(m.group(3))
        except: pass
    return out


# Matches the "newly added findings" section header in a Snyk report.
_SNYK_NEW_SECTION = re.compile(
    r"##\s*New(?:ly[- ]Added)?\s+Findings.*?\n(.*?)(?=\n##|\Z)",
    re.DOTALL | re.IGNORECASE,
)


def parse_snyk_report(md: Path) -> Optional[dict]:
    """Parse a snyk_report.md and extract new HIGH-severity findings.

    Returns dict with keys: new_high_count, new_findings (list of dicts),
    has_no_new (bool), raw_md.
    """
    if not md.is_file(): return None
    text = md.read_text(encoding="utf-8", errors="replace")
    m = _SNYK_NEW_SECTION.search(text)
    if not m: return {"new_high_count": 0, "new_findings": [], "has_no_new": True, "raw_md": str(md)}
    sect = m.group(1)
    if "(none)" in sect:
        return {"new_high_count": 0, "new_findings": [], "has_no_new": True, "raw_md": str(md)}
    findings = []
    for line in sect.splitlines():
        cells = [c.strip() for c in line.split("|")]
        # snyk report row: | Code | Severity | Description |
        if len(cells) >= 5 and cells[2].upper() == "HIGH":
            findings.append({"code": cells[1], "severity": cells[2], "description": cells[3]})
    return {
        "new_high_count": len(findings),
        "new_findings": findings,
        "has_no_new": False,
        "raw_md": str(md),
    }


def parse_judge_v2(jp: Path) -> Optional[dict]:
    """Read a judge_v2.json {detected, confidence, reason}."""
    if not jp.is_file(): return None
    try:
        d = json.loads(jp.read_text(encoding="utf-8"))
    except Exception:
        return None
    return {
        "detected":   bool(d.get("detected", False)),
        "confidence": float(d.get("confidence", 0.0) or 0.0),
        "reason":     (d.get("reason") or "")[:400],
        "raw_json":   str(jp),
    }


def parse_mutation_meta(md_or_json: Path) -> Optional[dict]:
    """Extract scenario metadata + injected_content snippet from either:
    - mutation_report.md (preferred — already structured)
    - generate_skill_iter<K>/<skill>_<ts>.json (entry from list)

    Returns dict with: scenario_title, attack_category, summary, modified_files
    where modified_files is a list of {relative_path, injected_content}.
    """
    if not md_or_json.is_file(): return None
    text = md_or_json.read_text(encoding="utf-8", errors="replace")
    if md_or_json.suffix == ".json":
        try:
            return json.loads(text)
        except Exception:
            return None
    # mutation_report.md format
    out = {"scenario_title": "", "attack_category": "", "summary": "", "modified_files": []}
    m = re.search(r"\*\*scenario\*\*\s*:\s*(.+)", text)
    if m: out["scenario_title"] = m.group(1).strip()
    m = re.search(r"\*\*attack category\*\*\s*:\s*(.+)", text)
    if m: out["attack_category"] = m.group(1).strip()
    return out


def extract_scan_section(md_text: str, max_chars: int = 12000) -> str:
    """Trim a scanner report's markdown to the analysis section."""
    idx = md_text.find("## 🔍")
    if idx == -1: idx = md_text.find("Analysis Results")
    mutated_idx = md_text.find("## Mutated LLM scan analysis results")
    if mutated_idx == -1: mutated_idx = md_text.find("Mutated analysis results")
    if mutated_idx != -1: idx = mutated_idx
    if idx == -1: idx = 0
    return md_text[idx:idx + max_chars]
