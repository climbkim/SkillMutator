# -*- coding: utf-8 -*-
"""Apply external (third-party) scanners to the SkillMutator benchmark.

Target scanners (no API key needed, static):
  - underhood_static : Under the Hood of SKILL.md (arXiv 2605.11418)
                       governance/clawhub_moderation/static_scan.py
  - sentry_static    : Sentry Skill Scanner (getsentry/skills)
                       skills/skill-scanner/scripts/scan_skill.py

Neither scanner was ever used in our evasion-refinement loop (C-3 response).

Usage:
  python run_external_scanners.py --dataset gpt-5.4
  python run_external_scanners.py --dataset gpt-5.4 --benign
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# ------------------------------------------------------------------ #
# Paths — resolved relative to this file's location (Review_4/harness/).
# ------------------------------------------------------------------ #
HERE = Path(__file__).resolve().parent
REVIEW4 = HERE.parent
SCANNER_DIR = REVIEW4 / "scanners"
ROOT = REVIEW4.parent                      # project root
BENCH = ROOT / "skillmutator-github" / "dataset"
BENIGN = ROOT / "skillmutator-github" / "skills"
OUTDIR = REVIEW4 / "results"

UNDERHOOD_PKG = SCANNER_DIR / "01_underhood" / "governance"
SENTRY_SCRIPT = (SCANNER_DIR / "02_sentry" / "skill-scanner"
                 / "scripts" / "scan_skill.py")
SKILLSCAN_SRC = SCANNER_DIR / "03_skillscan_nmitchem" / "src"

# SkillScan (NMitchem) requires Python 3.12 because of yara-python.
# Cisco also calls the pip-installed build (skill_scanner) of the same interpreter.
#   install: SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0 <py312> -m pip install scanners/04_cisco
# Set REVIEW4_PY312 to a Python 3.12 interpreter that has yara-python installed.
SKILLSCAN_PY = Path(os.getenv("REVIEW4_PY312", "python3"))

# Sentry scanner's structure-validation categories are not security detections, so exclude them
SENTRY_NONSECURITY_CATEGORIES = {"Validation", "Structure", "Metadata"}


# --------------------------------------------------------------------------- #
# Sample collection
# --------------------------------------------------------------------------- #
def collect_mutated(dataset: str) -> list[dict]:
    """List of mutated-skill samples in the benchmark."""
    base = BENCH / dataset / "result"
    out = []
    for md in sorted(base.glob("*/*/Stage4_Skill_Mutation/*/iter_*/skills/SKILL.md")):
        skill_dir = md.parent
        iter_dir = skill_dir.parent
        # .../result/<host>/<timestamp>/Stage4_Skill_Mutation/<category>/<iter>/skills/SKILL.md
        out.append({
            "sample_id": f"{dataset}/{md.parts[-7]}/{md.parts[-4]}/{iter_dir.name}",
            "dataset": dataset,
            "host_skill": md.parts[-7],
            "run_stamp": md.parts[-6],
            "attack_category": md.parts[-4],
            "iteration": iter_dir.name,
            "label": "malicious",
            "skill_dir": skill_dir,
        })
    return out


def collect_benign() -> list[dict]:
    """Original skills before mutation (for false-positive-rate measurement)."""
    out = []
    for md in sorted(BENIGN.glob("*/SKILL.md")):
        out.append({
            "sample_id": f"benign/{md.parent.name}",
            "dataset": "benign",
            "host_skill": md.parent.name,
            "attack_category": "-",
            "iteration": "-",
            "label": "benign",
            "skill_dir": md.parent,
        })
    return out


# --------------------------------------------------------------------------- #
# Scanner adapters
# --------------------------------------------------------------------------- #
def scan_underhood(skill_dir: Path) -> dict:
    """Under the Hood static scanner. status: clean / suspicious / malicious."""
    if str(UNDERHOOD_PKG) not in sys.path:
        sys.path.insert(0, str(UNDERHOOD_PKG))
    from clawhub_moderation.static_scan import scan_static  # noqa: PLC0415

    result = scan_static(skill_dir)[0]
    return {
        "verdict": result.status,
        "detected": result.status != "clean",
        "reason_codes": list(result.reason_codes),
        "n_findings": len(result.findings),
        "summary": result.summary,
    }


def scan_sentry(skill_dir: Path) -> dict:
    """Sentry static scanner. No native final verdict, so aggregate by severity."""
    proc = subprocess.run(
        [sys.executable, str(SENTRY_SCRIPT), str(skill_dir)],
        capture_output=True, text=True, timeout=180,
    )
    if proc.returncode not in (0, 1) or not proc.stdout.strip():
        return {"verdict": "error", "detected": False, "error": proc.stderr[-400:]}

    data = json.loads(proc.stdout)
    findings = data.get("findings", [])
    security = [f for f in findings
                if f.get("category") not in SENTRY_NONSECURITY_CATEGORIES]
    sev = {}
    for f in security:
        sev[f.get("severity", "?")] = sev.get(f.get("severity", "?"), 0) + 1

    high = sev.get("critical", 0) + sev.get("high", 0)
    return {
        # record both verdict criteria together so threshold sensitivity is visible
        "verdict": "flagged" if high else ("low_flag" if security else "clean"),
        "detected": high > 0,
        "detected_any": len(security) > 0,
        "severity_counts": sev,
        "n_findings": len(security),
        "n_findings_raw": len(findings),
        "categories": sorted({f.get("category", "?") for f in security}),
        "has_scripts": data.get("structure", {}).get("has_scripts"),
        "n_script_files": len(data.get("structure", {}).get("script_files", [])),
    }


def scan_skillscan(skill_dir: Path) -> dict:
    """SkillScan (NMitchem). A static scanner that reads only SKILL.md. The LLM stage is not used."""
    env = dict(os.environ, PYTHONPATH=str(SKILLSCAN_SRC))
    proc = subprocess.run(
        [str(SKILLSCAN_PY), "-m", "skillscan.cli", "audit", str(skill_dir),
         "--format", "json", "--no-color"],
        capture_output=True, text=True, timeout=180, env=env,
    )
    out = proc.stdout.strip()
    if not out or not out.startswith("{"):
        return {"verdict": "error", "detected": False,
                "error": (proc.stderr or out)[-400:]}

    data = json.loads(out)
    findings = data.get("findings", [])
    sev = {}
    for f in findings:
        k = str(f.get("severity", "?")).upper()
        sev[k] = sev.get(k, 0) + 1
    return {
        # use the tool's own verdict (risk_score >= threshold) as the primary criterion
        "verdict": "flagged" if not data.get("passed", True) else "clean",
        "detected": not data.get("passed", True),
        "detected_any": len(findings) > 0,
        "risk_score": data.get("risk_score"),
        "threshold": data.get("threshold"),
        "severity_counts": sev,
        "n_findings": len(findings),
        "analyzers": sorted({f.get("analyzer", "?") for f in findings}),
    }


def scan_cisco(skill_dir: Path) -> dict:
    """Cisco AI Defense Skill Scanner. Static (YARA+rules) + behavioral dataflow.

    --use-llm / --use-aidefense require an external API, so they are not used.
    """
    proc = subprocess.run(
        [str(SKILLSCAN_PY), "-m", "skill_scanner.cli.cli", "scan", str(skill_dir),
         "--use-behavioral", "--format", "json"],
        capture_output=True, text=True, timeout=300,
    )
    out = proc.stdout
    i = out.find("{")
    if i < 0:
        return {"verdict": "error", "detected": False,
                "error": (proc.stderr or out)[-400:]}

    data = json.loads(out[i:])
    findings = data.get("findings", [])
    # policy violations such as a missing license are not security detections, so exclude them
    security = [f for f in findings if f.get("category") != "policy_violation"]
    sev = {}
    for f in security:
        k = str(f.get("severity", "?")).upper()
        sev[k] = sev.get(k, 0) + 1
    high = sev.get("CRITICAL", 0) + sev.get("HIGH", 0)
    return {
        "verdict": "flagged" if high else ("low_flag" if security else "clean"),
        "detected": high > 0,
        "detected_any": len(security) > 0,
        "detected_tool_is_safe": not data.get("is_safe", True),
        "max_severity": data.get("max_severity"),
        "severity_counts": sev,
        "n_findings": len(security),
        "analyzers": sorted({f.get("analyzer", "?") for f in security}),
        "behavioral_hits": sum(1 for f in security if f.get("analyzer") == "behavioral"),
    }


SCANNERS = {
    "underhood_static": scan_underhood,
    "sentry_static": scan_sentry,
    "skillscan": scan_skillscan,
    "cisco": scan_cisco,
}


# --------------------------------------------------------------------------- #
# Execution
# --------------------------------------------------------------------------- #
def staged_copy(sample: dict, tmp: Path) -> Path:
    """Copy so that the skill directory name is the actual skill name.

    The benchmark places skills at .../iter_N/skills/, but since the directory name is 'skills',
    name-mismatch false positives occur systematically. This mimics the real installed form.
    """
    dst = tmp / sample["host_skill"]
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(sample["skill_dir"], dst)
    return dst


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="gpt-5.4")
    ap.add_argument("--benign", action="store_true", help="also evaluate the original benign skills")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    samples = collect_mutated(args.dataset)
    if args.benign:
        samples += collect_benign()
    if args.limit:
        samples = samples[: args.limit]

    print(f"samples {len(samples)} · scanners {len(SCANNERS)}", flush=True)
    OUTDIR.mkdir(parents=True, exist_ok=True)

    rows, raw = [], []
    with tempfile.TemporaryDirectory(prefix="extscan_") as td:
        tmp = Path(td)
        for i, s in enumerate(samples, 1):
            staged = staged_copy(s, tmp)
            row = {k: s.get(k, "-") for k in
                   ("sample_id", "dataset", "host_skill", "run_stamp",
                    "attack_category", "iteration", "label")}
            for name, fn in SCANNERS.items():
                try:
                    r = fn(staged)
                except Exception as exc:  # noqa: BLE001
                    r = {"verdict": "error", "detected": False, "error": repr(exc)[:300]}
                row[f"{name}_verdict"] = r.get("verdict")
                row[f"{name}_detected"] = int(bool(r.get("detected")))
                if "detected_any" in r:
                    row[f"{name}_detected_any"] = int(bool(r["detected_any"]))
                raw.append({"sample_id": s["sample_id"], "scanner": name, **r})
            rows.append(row)
            if i % 10 == 0 or i == len(samples):
                print(f"  {i}/{len(samples)}", flush=True)

    tag = args.dataset + ("_with_benign" if args.benign else "")
    csv_path = OUTDIR / f"external_scan_{tag}.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    (OUTDIR / f"external_scan_{tag}_raw.json").write_text(
        json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")

    # Summary
    print("\n" + "=" * 62)
    for label in ("malicious", "benign"):
        sub = [r for r in rows if r["label"] == label]
        if not sub:
            continue
        n = len(sub)
        kind = "detection rate (TPR)" if label == "malicious" else "false-positive rate (FPR)"
        print(f"\n[{label}] n={n}   {kind}")
        for name in SCANNERS:
            d = sum(r[f"{name}_detected"] for r in sub)
            line = f"  {name:20s} {d:4d}/{n}  = {100*d/n:5.1f}%"
            key = f"{name}_detected_any"
            if key in sub[0]:
                da = sum(r[key] for r in sub)
                line += f"   (any-severity {100*da/n:5.1f}%)"
            print(line)
    print("\nsaved:", csv_path)


if __name__ == "__main__":
    main()
