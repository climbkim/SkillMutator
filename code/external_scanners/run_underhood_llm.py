# -*- coding: utf-8 -*-
"""Apply the moderation pipeline of Under the Hood of SKILL.md (arXiv 2605.11418)
to the SkillMutator benchmark — static + LLM stages.

The VirusTotal stage is excluded. run_submit_pipeline forces VT_API_KEY, but
since run_llm_security_eval takes scan_static's output directly, only the two stages can be
connected directly. VT is file-hash reputation, so newly created skills have no signal.

The model is specified with --model rather than the code default (gpt-5-mini).

Usage:
  python run_underhood_llm.py --dataset gpt-5.4 --benign --model gpt-5.4
  python run_underhood_llm.py --limit 2 --model gpt-5.4        # smoke test
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REVIEW4 = HERE.parent
ROOT = REVIEW4.parent
ENV_FILE = ROOT / "skillmutator-github" / ".env"
OUTDIR = REVIEW4 / "results"
CACHE = OUTDIR / "llm_cache"
UNDERHOOD_PKG = REVIEW4 / "scanners" / "01_underhood" / "governance"

sys.path.insert(0, str(UNDERHOOD_PKG))
sys.path.insert(0, str(HERE))

from run_external_scanners import collect_benign, collect_mutated  # noqa: E402


def load_env() -> None:
    if not ENV_FILE.exists():
        return
    for line in io.open(ENV_FILE, encoding="utf-8", errors="replace").read().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def cache_key(sample_id: str, model: str) -> Path:
    h = hashlib.sha256(f"{sample_id}|{model}".encode()).hexdigest()[:24]
    return CACHE / f"{h}.json"


def evaluate(sample: dict, staged: Path, model: str) -> dict:
    """Static scan -> LLM evaluation -> aggregate the two stages."""
    from clawhub_moderation import llm as llm_mod
    from clawhub_moderation.llm import run_llm_security_eval
    from clawhub_moderation.models import VtAnalysis
    from clawhub_moderation.moderation import build_moderation_snapshot
    from clawhub_moderation.static_scan import scan_static

    # The constant is hardcoded to us.api.openai.com (a regional hostname), so a standard key gives 401.
    # Without touching their source, we override only the module constant.
    llm_mod.OPENAI_RESPONSES_URL = os.getenv(
        "OPENAI_RESPONSES_URL", "https://api.openai.com/v1/responses")

    static, fm, files, skill_md, file_texts = scan_static(staged)
    llm = run_llm_security_eval(
        skill_dir=staged,
        skill_name=str(fm.get("name")) if fm.get("name") is not None else None,
        display_name=str(fm.get("displayName") or fm.get("name") or ""),
        summary=str(fm.get("description")) if fm.get("description") is not None else None,
        version=str(fm.get("version")) if fm.get("version") is not None else None,
        frontmatter=fm,
        files=files,
        skill_md_text=skill_md,
        file_texts=file_texts,
        timeout=180.0,
    )
    # VT is not run. With status='pending' it contributes no code to the aggregate.
    final = build_moderation_snapshot(static, VtAnalysis(status="pending"), llm)

    return {
        "static_status": static.status,
        "static_codes": list(static.reason_codes),
        "llm_status": llm.status,
        "llm_verdict": llm.verdict,
        "llm_confidence": llm.confidence,
        "llm_model": llm.model,
        "llm_summary": (llm.summary or "")[:600],
        "dimensions": {k: {"status": d.status, "detail": (d.detail or "")[:300]}
                       for k, d in llm.dimensions.items()},
        "final_verdict": final.verdict,
        "final_codes": list(final.reason_codes),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="gpt-5.4")
    ap.add_argument("--benign", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--model", default="gpt-5.4")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--no-truncate", action="store_true",
                    help="lift all SKILL.md/file/total caps (original is 6K/10K/50K)")
    args = ap.parse_args()

    load_env()
    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY not found")
    os.environ["OPENAI_EVAL_MODEL"] = args.model

    # Cap condition. Reflected in the cache key too so the two conditions don't mix.
    cond = "trunc"
    if args.no_truncate:
        cond = "notrunc"
        big = str(10 ** 9)
        os.environ["UH_MAX_SKILL_MD_CHARS"] = big
        os.environ["UH_MAX_FILE_CHARS"] = big
        os.environ["UH_MAX_TOTAL_CHARS"] = big
    model_tag = f"{args.model}__{cond}"

    samples = collect_mutated(args.dataset)
    if args.benign:
        samples += collect_benign()
    if args.limit:
        samples = samples[: args.limit]

    CACHE.mkdir(parents=True, exist_ok=True)
    OUTDIR.mkdir(parents=True, exist_ok=True)
    print(f"samples {len(samples)} · model {args.model} · workers {args.workers}", flush=True)

    tmproot = Path(tempfile.mkdtemp(prefix="uhllm_"))
    done = [0]
    t0 = time.time()

    def work(idx_sample):
        i, s = idx_sample
        ck = cache_key(s["sample_id"], model_tag)
        if ck.exists():
            res = json.loads(ck.read_text(encoding="utf-8"))
        else:
            staged = tmproot / f"w{i}" / s["host_skill"]
            staged.parent.mkdir(parents=True, exist_ok=True)
            if staged.exists():
                shutil.rmtree(staged)
            shutil.copytree(s["skill_dir"], staged)
            try:
                res = evaluate(s, staged, args.model)
            except Exception as exc:  # noqa: BLE001
                res = {"error": repr(exc)[:400], "llm_status": "error",
                       "final_verdict": "error", "static_status": "?"}
            ck.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        done[0] += 1
        if done[0] % 10 == 0 or done[0] == len(samples):
            print(f"  {done[0]}/{len(samples)}  ({time.time()-t0:.0f}s)", flush=True)
        return s, res

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(work, enumerate(samples)))

    shutil.rmtree(tmproot, ignore_errors=True)

    rows = []
    for s, r in results:
        row = {k: s.get(k, "-") for k in
               ("sample_id", "dataset", "host_skill", "attack_category", "label")}
        row.update({
            "static_status": r.get("static_status"),
            "llm_status": r.get("llm_status"),
            "llm_verdict": r.get("llm_verdict"),
            "final_verdict": r.get("final_verdict"),
            # if the registry is not clean it is a block/warn target -> counted as detected
            "detected": int(r.get("final_verdict") not in (None, "clean", "error")),
            "llm_detected": int(r.get("llm_status") not in (None, "clean", "error", "pending")),
            "error": r.get("error", ""),
        })
        for dim in ("purpose_capability", "instruction_scope", "install_mechanism",
                    "environment_proportionality", "persistence_privilege"):
            row[f"dim_{dim}"] = (r.get("dimensions") or {}).get(dim, {}).get("status", "")
        rows.append(row)

    tag = f"{args.dataset}{'_with_benign' if args.benign else ''}_{model_tag}"
    csv_path = OUTDIR / f"underhood_llm_{tag}.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print("\n" + "=" * 62)
    for label in ("malicious", "benign"):
        sub = [r for r in rows if r["label"] == label]
        if not sub:
            continue
        n = len(sub)
        errs = sum(1 for r in sub if r["error"])
        kind = "detection rate (TPR)" if label == "malicious" else "false-positive rate (FPR)"
        print(f"\n[{label}] n={n}  errors={errs}   {kind}")
        for key, name in (("llm_detected", "LLM stage only"), ("detected", "static+LLM aggregate")):
            d = sum(r[key] for r in sub)
            print(f"  {name:14s} {d:4d}/{n} = {100*d/n:5.1f}%")
        vc = {}
        for r in sub:
            vc[r["final_verdict"]] = vc.get(r["final_verdict"], 0) + 1
        print("  final verdict distribution:", vc)
    print("\nsaved:", csv_path)


if __name__ == "__main__":
    main()
