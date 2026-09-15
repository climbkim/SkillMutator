# -*- coding: utf-8 -*-
"""Generate a table of per-scanner verdict-level distributions and per-criterion (self/unified) figures.

Output: results/LEVELS.md

Each scanner's output scheme differs, so collapsing them into a single 'detection rate' metric distorts the comparison.
We report the level distribution as-is, alongside each tool's own verdict criterion and a one-step-relaxed criterion.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path

REVIEW4 = Path(__file__).resolve().parent.parent
R = REVIEW4 / "results"
B = REVIEW4.parent / "skillmutator-github" / "dataset" / "gpt-5.4" / "result"
HOSTS = {p.name for p in B.iterdir() if p.is_dir()}

SEV_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO", "SAFE"]
CH = {"CRITICAL", "HIGH"}
CHM = {"CRITICAL", "HIGH", "MEDIUM"}


def load(name):
    return list(csv.DictReader(io.open(R / name, encoding="utf-8-sig")))


def split(rows):
    return ([r for r in rows if r["label"] == "malicious"],
            [r for r in rows if r["label"] == "benign" and r["host_skill"] in HOSTS])


_raw = {}
for x in json.loads((R / "external_scan_gpt-5.4_with_benign_raw.json").read_text(encoding="utf-8")):
    _raw.setdefault(x["scanner"], {})[x["sample_id"]] = x


def cache(sid, name):
    k = hashlib.sha256(f"{sid}|{name}|gpt-5.4".encode()).hexdigest()[:24]
    p = R / "llm_modes_cache" / f"{k}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def has_sev(counts, keys):
    c = {str(k).upper(): v for k, v in (counts or {}).items()}
    return any(c.get(k) for k in keys)


def max_sev(counts):
    c = {str(k).upper(): v for k, v in (counts or {}).items()}
    for s in SEV_ORDER:
        if c.get(s):
            return s
    return "SAFE"


S = load("external_scan_gpt-5.4_with_benign.csv")
M = load("llm_scanners_gpt-5.4_with_benign_gpt-5.4.csv")
U1 = load("underhood_llm_gpt-5.4_with_benign_gpt-5.4.csv")
U2 = load("underhood_llm_gpt-5.4_with_benign_gpt-5.4__notrunc.csv")


def risk_band(v):
    v = v or 0
    if v >= 6:
        return "risk >= 6.0"
    if v >= 4:
        return "risk 4.0-5.9"
    if v >= 2:
        return "risk 2.0-3.9"
    if v > 0:
        return "risk 0.1-1.9"
    return "risk 0"


RISK_BANDS = ["risk >= 6.0", "risk 4.0-5.9", "risk 2.0-3.9", "risk 0.1-1.9", "risk 0"]

# (title, verdict-scheme description, level list, table, level extraction fn)
LEVEL_TABLES = [
    ("Under the Hood — static", "3-level verdict (clean / suspicious / malicious)",
     ["malicious", "suspicious", "clean"], S,
     lambda r: r["underhood_static_verdict"]),
    ("Under the Hood — +LLM (original truncated)", "3-level verdict",
     ["malicious", "suspicious", "benign"], U1, lambda r: r["llm_verdict"]),
    ("Under the Hood — +LLM (truncation lifted)", "3-level verdict",
     ["malicious", "suspicious", "benign"], U2, lambda r: r["llm_verdict"]),
    ("Sentry — static", "no final verdict. aggregated by the highest severity of findings",
     SEV_ORDER, S,
     lambda r: max_sev(_raw["sentry_static"][r["sample_id"]].get("severity_counts"))),
    ("Sentry — +LLM", "5-level Risk Level (their SKILL.md output format)",
     ["critical", "high", "medium", "low", "clean"], M,
     lambda r: r["sentry_full_verdict"]),
    ("Cisco — static+behavioral", "binary is_safe + 6-level max_severity",
     SEV_ORDER, S,
     lambda r: max_sev(_raw["cisco"][r["sample_id"]].get("severity_counts"))),
    ("Cisco — +LLM (7 analyzers)", "binary is_safe + 6-level max_severity",
     SEV_ORDER, M,
     lambda r: cache(r["sample_id"], "cisco_full").get("max_severity") or "SAFE"),
    ("SkillScan — static", "continuous risk_score -> binary passed (threshold 6.0)",
     RISK_BANDS, S,
     lambda r: risk_band(_raw["skillscan"][r["sample_id"]].get("risk_score"))),
    ("SkillScan — +LLM", "continuous risk_score -> binary passed (threshold 6.0)",
     RISK_BANDS, M,
     lambda r: risk_band(cache(r["sample_id"], "skillscan_llm").get("risk_score"))),
]

# (scanner, configuration, table, self-criterion name, self fn, unified-criterion name, unified fn)
# Unified criterion = severity HIGH or above. Since each tool's verdict scheme differs and distorts comparison,
# we also include values aligned to the same severity floor (HIGH) across all scanners.
CRIT_ROWS = [
    ("Under the Hood", "static", S,
     "malicious", lambda r: r["underhood_static_verdict"] == "malicious",
     "suspicious or above †", lambda r: r["underhood_static_verdict"] != "clean"),
    ("Under the Hood", "+LLM (original truncated)", U1,
     "malicious", lambda r: r["llm_verdict"] == "malicious",
     "suspicious or above †", lambda r: r["llm_verdict"] != "benign"),
    ("Under the Hood", "+LLM (truncation lifted)", U2,
     "malicious", lambda r: r["llm_verdict"] == "malicious",
     "suspicious or above †", lambda r: r["llm_verdict"] != "benign"),
    ("Sentry", "static", S,
     "CRITICAL/HIGH", lambda r: has_sev(_raw["sentry_static"][r["sample_id"]].get("severity_counts"), CH),
     "HIGH or above", lambda r: has_sev(_raw["sentry_static"][r["sample_id"]].get("severity_counts"), CH)),
    ("Sentry", "+LLM", M,
     "Critical+High", lambda r: r["sentry_full_verdict"] in ("critical", "high"),
     "HIGH or above", lambda r: r["sentry_full_verdict"] in ("critical", "high")),
    ("Cisco", "static+behavioral", S,
     "is_safe=False", lambda r: has_sev(_raw["cisco"][r["sample_id"]].get("severity_counts"), CH),
     "HIGH or above", lambda r: has_sev(_raw["cisco"][r["sample_id"]].get("severity_counts"), CH)),
    ("Cisco", "+LLM (7 analyzers)", M,
     "is_safe=False", lambda r: cache(r["sample_id"], "cisco_full").get("max_severity") in CH,
     "HIGH or above", lambda r: has_sev(cache(r["sample_id"], "cisco_full").get("severity_counts"), CH)),
    ("SkillScan", "static", S,
     "risk>=6.0", lambda r: (_raw["skillscan"][r["sample_id"]].get("risk_score") or 0) >= 6,
     "HIGH or above", lambda r: has_sev(_raw["skillscan"][r["sample_id"]].get("severity_counts"), CH)),
    ("SkillScan", "+LLM", M,
     "risk>=6.0", lambda r: (cache(r["sample_id"], "skillscan_llm").get("risk_score") or 0) >= 6,
     "risk>=6.0 ‡", lambda r: (cache(r["sample_id"], "skillscan_llm").get("risk_score") or 0) >= 6),
]


def main() -> None:
    L, A = [], None
    L = []
    A = L.append
    A("# Per-scanner verdict-level distribution and per-criterion figures\n")
    A(f"Mutations **76** / control **{len(HOSTS)}** (originals of the host skills used for mutation).")
    A("None of the configurations were ever used in our evasion-refinement loop. The judge model is `gpt-5.4`.\n")

    A("## 1. Each scanner's output scheme\n")
    A("**Not a single tool produces a binary mal/benign.** All four have different schemes.\n")
    A("| scanner | output | final verdict rule |")
    A("|---|---|---|")
    A("| Under the Hood | 3-level `clean`/`suspicious`/`malicious` | malicious if there is a `malicious.` prefix code, "
      "suspicious if there is any code, otherwise clean |")
    A("| Sentry (script) | findings only. **no final verdict field** | — (their SKILL.md defines it as Phase 2 clue collection) |")
    A("| Sentry (full) | 5-level `Critical`/`High`/`Medium`/`Low`/`Clean` | the agent decides after an 8-step workflow. "
      "In Confidence Levels, MEDIUM=\"Needs verification\", LOW=\"Do not report\" |")
    A("| SkillScan | continuous `risk_score` -> binary `passed` | `risk_score >= threshold`(default 6.0) |")
    A("| Cisco | binary `is_safe` + 6-level `max_severity` | if there is any CRITICAL/HIGH finding, "
      "`is_safe=False`. **MEDIUM or below is safe no matter how many** |")

    A("\n## 2. Distribution by level\n")
    A("The numbers are `mutations 76` / `originals 17`.\n")
    for title, scheme, levels, rows, fn in LEVEL_TABLES:
        mal, ben = split(rows)
        cm, cb = Counter(fn(r) for r in mal), Counter(fn(r) for r in ben)
        A(f"### {title}\n")
        A(f"*{scheme}*\n")
        A("| level | mutations 76 | originals 17 |")
        A("|---|---|---|")
        for lv in levels:
            A(f"| {lv} | {cm.get(lv, 0)} | {cb.get(lv, 0)} |")
        A("")

    A("## 3. Self criterion vs HIGH-unified criterion\n")
    A("`self criterion` is the verdict rule each tool defines on its own. Since each tool's scheme differs and comparing them directly"
      " is distorting, we also include values aligned to a severity **HIGH floor**.\n")
    A("| scanner | configuration | self criterion | detected | false-positive | gap | HIGH-unified criterion | detected | false-positive | gap |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    for name, mode, rows, sn, sf, ln, lf in CRIT_ROWS:
        mal, ben = split(rows)
        cells = []
        for f in (sf, lf):
            tp = sum(1 for r in mal if f(r))
            fp = sum(1 for r in ben if f(r))
            t, fr = 100 * tp / len(mal), 100 * fp / len(ben)
            cells.append((f"{t:.1f}% ({tp}/{len(mal)})",
                          f"{fr:.1f}% ({fp}/{len(ben)})", f"{t-fr:.1f}pp"))
        A(f"| {name} | {mode} | `{sn}` | {cells[0][0]} | {cells[0][1]} | {cells[0][2]} "
          f"| `{ln}` | {cells[1][0]} | {cells[1][1]} | {cells[1][2]} |")

    A("\n† Under the Hood has only 3 levels (clean/suspicious/malicious), so there is no grade corresponding to HIGH."
      " We used the middle grade `suspicious` instead — a **more lenient** criterion than other scanners' HIGH.\n")
    A("‡ SkillScan +LLM does not record a severity distribution at run time, so only the risk-score criterion can be used."
      " It is not directly comparable to the static configuration's HIGH criterion.\n")

    A("\n## 4. Interpretation\n")
    A("**Zero mutations reached a blocking grade.** Under the Hood is `malicious` 0/76 in all three configurations. "
      "A `malicious` verdict requires a `malicious.` prefix code (crypto mining · install terminal payload · "
      "known blocked signature), which are all blatant signatures. Our mutations do not "
      "create such signatures, so **they cannot reach a blocking grade by taxonomy design, not by threshold.**\n")
    A("**Most misses are not \"failed to see\" but \"below grade.\"** Cisco +LLM issues findings on "
      "67 of 76 mutations (only 9 SAFE), but since `is_safe` looks only at CRITICAL/HIGH, only 11 are flagged. "
      "**42 are trapped at MEDIUM.** Each modality is individually coherent, so the grade does not rise.\n")
    A("**Loosening the criterion collapses discriminative power.** Sentry +LLM detects 89.5% if you count down to Medium, but "
      "13 of 17 originals (76.5%) are also caught, so the gap actually shrinks from 19.2pp -> 13.0pp. Cisco static "
      "has a **negative** gap at MEDIUM or above.\n")
    A("**Sentry static has no middle grade.** It is either CRITICAL/HIGH or SAFE, so the self criterion and unified criterion "
      "become the same value.\n")
    A("**Beware criterion asymmetry.** In this report's main table (SUMMARY.md), only Under the Hood counts `suspicious or above` "
      "as detected, while the other three effectively require HIGH or above. If Under the Hood is aligned to the same criterion, it is "
      "**0%**. This must be noted in a footnote when included in the paper.\n")

    (R / "LEVELS.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
