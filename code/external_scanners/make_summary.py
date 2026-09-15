# -*- coding: utf-8 -*-
"""Review_4 final summary — 4 scanners × (static / max performance) results in one table.

The false-positive-rate denominator is **the originals of the 17 host skills used for mutation**.
`skillmutator-github/skills/` has 46, but 29 are a separate distribution not used for mutation,
so they must not be mixed in (their figures are given separately in an appendix table).

Output: results/SUMMARY.md
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter, defaultdict
from pathlib import Path

REVIEW4 = Path(__file__).resolve().parent.parent
R = REVIEW4 / "results"
B = REVIEW4.parent / "skillmutator-github" / "dataset" / "gpt-5.4" / "result"

CODE_EXT = {".py", ".js", ".ts", ".sh", ".bash", ".rb", ".go", ".mjs", ".cjs",
            ".jsx", ".tsx", ".ps1", ".bat", ".html", ".php", ".java", ".cs"}

STATIC = "external_scan_gpt-5.4_with_benign.csv"
LLMSC = "llm_scanners_gpt-5.4_with_benign_gpt-5.4.csv"
LLMSC1 = "llm_scanners_gpt-5.4_with_benign_gpt-5.4_run1.csv"
UH_T = "underhood_llm_gpt-5.4_with_benign_gpt-5.4.csv"
UH_N = "underhood_llm_gpt-5.4_with_benign_gpt-5.4__notrunc.csv"

# (scanner, configuration, file, verdict fn, read scope, short name)
CONFIGS = [
    ("SkillScan (NMitchem)", "static", STATIC,
     lambda r: r["skillscan_detected"] == "1", "SKILL.md only", "SkillScan"),
    ("SkillScan (NMitchem)", "+LLM", LLMSC,
     lambda r: r["skillscan_llm_detected"] == "1", "SKILL.md only", "SkillScan+L"),
    ("Sentry Skill Scanner", "static", STATIC,
     lambda r: r["sentry_static_detected"] == "1",
     "SKILL.md + scripts/ top level", "Sentry"),
    ("Sentry Skill Scanner", "+LLM (Crit+High)", LLMSC,
     lambda r: r["sentry_full_verdict"] in ("critical", "high"),
     "all files + 8-step workflow", "Sentry+L"),
    ("Cisco Skill Scanner", "static+behavioral", STATIC,
     lambda r: r["cisco_detected"] == "1", "all files + dataflow", "Cisco"),
    ("Cisco Skill Scanner", "+LLM (7 analyzers)", LLMSC,
     lambda r: r["cisco_full_detected"] == "1", "all files + dataflow", "Cisco+L"),
    ("Under the Hood", "static", STATIC,
     lambda r: r["underhood_static_detected"] == "1", "all files recursive", "UH"),
    ("Under the Hood", "+LLM (original truncated)", UH_T,
     lambda r: r["detected"] == "1", "all files + 5-dimension verdict", "UH+L"),
    ("Under the Hood", "+LLM (truncation lifted)", UH_N,
     lambda r: r["detected"] == "1", "all files + 5-dimension verdict", "UH+L(no-trunc)"),
]


def load(name):
    p = R / name
    return list(csv.DictReader(io.open(p, encoding="utf-8-sig"))) if p.exists() else []


def main() -> None:
    hosts = {p.name for p in B.iterdir() if p.is_dir()}
    tables = {n: load(n) for n in {c[2] for c in CONFIGS}}

    L, A = [], None
    L = []
    A = L.append
    A("# External scanner evaluation — SkillMutator benchmark (gpt-5.4 oracle)\n")
    A(f"Mutations **76** / control **{len(hosts)}** (originals of the host skills used for mutation).")
    A("None of the configurations were ever used in our evasion-refinement loop.\n")
    A("| scanner | configuration | read scope | detection rate | false-positive rate | gap |")
    A("|---|---|---|---|---|---|")

    for name, mode, fname, pred, scope, _s in CONFIGS:
        rows = tables.get(fname, [])
        if not rows:
            A(f"| {name} | {mode} | {scope} | (not run) | (not run) | — |")
            continue
        mal = [r for r in rows if r["label"] == "malicious"]
        ben = [r for r in rows if r["label"] == "benign" and r["host_skill"] in hosts]
        tp = sum(1 for r in mal if pred(r))
        fp = sum(1 for r in ben if pred(r))
        t, f = 100 * tp / len(mal), 100 * fp / len(ben)
        A(f"| {name} | {mode} | {scope} | **{t:.1f}%** ({tp}/{len(mal)}) "
          f"| {f:.1f}% ({fp}/{len(ben)}) | {t-f:.1f}pp |")

    # Reference: 29 non-host
    A("\n### Reference — false-positive rate on the 29 skills not used for mutation\n")
    A("`skills/` has 46, but 29 are a separate distribution. They must not be averaged together.\n")
    A("| scanner · configuration | host originals 17 | non-host 29 |")
    A("|---|---|---|")
    for name, mode, fname, pred, _sc, _s in CONFIGS:
        rows = tables.get(fname, [])
        if not rows:
            continue
        b17 = [r for r in rows if r["label"] == "benign" and r["host_skill"] in hosts]
        b29 = [r for r in rows if r["label"] == "benign" and r["host_skill"] not in hosts]
        if not b29:
            continue
        f17 = sum(1 for r in b17 if pred(r))
        f29 = sum(1 for r in b29 if pred(r))
        A(f"| {name} · {mode} | {100*f17/len(b17):.1f}% ({f17}/{len(b17)}) "
          f"| {100*f29/len(b29):.1f}% ({f29}/{len(b29)}) |")

    # Run-to-run variation (3 LLM scanners)
    r1 = load(LLMSC1)
    r2 = tables.get(LLMSC, [])
    if r1 and r2:
        A("\n## Run-to-run verdict variation (same input, temperature 0.0)\n")
        A("LLM-based configurations give different verdicts on the same input. A single run's value must not be used as-is.\n")
        A("| configuration | run1 detection rate | run2 detection rate | samples whose verdict flipped |")
        A("|---|---|---|---|")
        k1 = {r["sample_id"]: r for r in r1}
        for col, label in (("sentry_full_verdict", "Sentry +LLM (Crit+High)"),
                           ("skillscan_llm_detected", "SkillScan +LLM"),
                           ("cisco_full_detected", "Cisco +LLM")):
            if col not in r2[0]:
                continue
            if col.endswith("_verdict"):
                f = lambda r: r[col] in ("critical", "high")  # noqa: E731
            else:
                f = lambda r: r[col] == "1"  # noqa: E731
            m2 = [r for r in r2 if r["label"] == "malicious"]
            m1 = [k1[r["sample_id"]] for r in m2 if r["sample_id"] in k1]
            flip = sum(1 for r in m2
                       if r["sample_id"] in k1 and f(r) != f(k1[r["sample_id"]]))
            A(f"| {label} | {100*sum(1 for r in m1 if f(r))/len(m1):.1f}% "
              f"| {100*sum(1 for r in m2 if f(r))/len(m2):.1f}% | {flip}/{len(m2)} |")

    # Breakdown by payload location
    A("\n## Breakdown by payload location (C-8 response)\n")
    raw_p = R / "external_scan_gpt-5.4_with_benign_raw.json"
    sentry_raw = {}
    if raw_p.exists():
        for x in json.loads(raw_p.read_text(encoding="utf-8")):
            if x.get("scanner") == "sentry_static":
                sentry_raw[x["sample_id"]] = x
    idx = {}
    for md in B.glob("*/*/Stage4_Skill_Mutation/*/iter_*/skills/SKILL.md"):
        idx[(md.parts[-7], md.parts[-4], md.parts[-3])] = md.parent

    A("| mutation type | n |" + "".join(f" {c[5]} |" for c in CONFIGS))
    A("|---" * (2 + len(CONFIGS)) + "|")
    counts, buckets = defaultdict(int), defaultdict(lambda: defaultdict(int))
    base = tables[STATIC]
    for r in [x for x in base if x["label"] == "malicious"]:
        d = idx.get((r["host_skill"], r["attack_category"], r["iteration"]))
        hs = sentry_raw.get(r["sample_id"], {}).get("has_scripts")
        if hs:
            b = "has scripts/"
        elif d and any(p.suffix.lower() in CODE_EXT for p in d.rglob("*") if p.is_file()):
            b = "code present but outside scripts/"
        else:
            b = "SKILL.md/docs only"
        counts[b] += 1
        for name, mode, fname, pred, _sc, short in CONFIGS:
            rows = tables.get(fname, [])
            src = next((x for x in rows if x["sample_id"] == r["sample_id"]), None)
            if src:
                buckets[b][short] += int(bool(pred(src)))
    for b in sorted(counts, key=lambda k: -counts[k]):
        A(f"| {b} | {counts[b]} |" + "".join(f" {buckets[b][c[5]]} |" for c in CONFIGS))

    (R / "SUMMARY.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
