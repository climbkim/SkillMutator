"""ClawHub registry backend for the community-skill crawler.

`crawl(target_count, output_dir)` reads a ClawHub manifest CSV (the columns
`slug, ..., pools, version, ..., api_url, ...` shipped as
``artifact/data/clawhub/clawhub_skills.csv``) and, for each selected skill,
fetches its ``SKILL.md`` from the public ClawHub API, verifying it against the
per-file sha256 in the version manifest. It writes:

    <output_dir>/<slug>/SKILL.md
    <output_dir>/<slug>/_clawhub_manifest.json   # provenance: full file list + sha256

The public ClawHub API exposes the SKILL.md body (via the skill's `description`)
and a file manifest with sha256 for every file, but NOT the raw bytes of the
other files. SKILL.md alone is a valid mutation target; the full skill bodies
are available through the ClawHub web UI or the authors' on-request corpus.

Manifest location (first hit wins):
  1. $SKILLMUTATOR_CLAWHUB_CSV (explicit path)
  2. a `data/clawhub/clawhub_skills.csv` or `artifact/data/clawhub/clawhub_skills.csv`
     found by walking up from this file.
Optional pool filter: $SKILLMUTATOR_CLAWHUB_POOL (e.g. "clean_175"); only rows
whose `pools` field contains it are considered.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

_API = "https://clawhub.ai/api/v1/skills"
_UA = {"User-Agent": "skillmutator-crawler/1.0"}


def _get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _find_manifest() -> Path | None:
    env = os.environ.get("SKILLMUTATOR_CLAWHUB_CSV")
    if env:
        p = Path(env).expanduser()
        return p if p.is_file() else None
    here = Path(__file__).resolve()
    rels = (
        Path("data") / "clawhub" / "clawhub_skills.csv",
        Path("artifact") / "data" / "clawhub" / "clawhub_skills.csv",
    )
    for base in [here, *here.parents]:
        for rel in rels:
            cand = base / rel
            if cand.is_file():
                return cand
    return None


def crawl(target_count: int, output_dir: str) -> None:
    manifest = _find_manifest()
    if manifest is None:
        print(
            "[clawhub] no manifest CSV found. Set $SKILLMUTATOR_CLAWHUB_CSV to a "
            "ClawHub skills CSV (columns include slug, version, api_url), e.g. "
            "artifact/data/clawhub/clawhub_skills.csv.",
            file=sys.stderr,
        )
        return
    pool = os.environ.get("SKILLMUTATOR_CLAWHUB_POOL", "").strip()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    print(f"[clawhub] manifest: {manifest}")
    if pool:
        print(f"[clawhub] pool filter: {pool}")

    with manifest.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    if pool:
        rows = [r for r in rows if pool in (r.get("pools") or "")]

    want = target_count if (target_count and target_count > 0) else len(rows)
    written = failed = 0
    for row in rows:
        if written >= want:
            break
        slug = (row.get("slug") or "").strip()
        version = (row.get("version") or "").strip()
        api_url = (row.get("api_url") or "").strip()
        if not slug:
            continue
        try:
            # version manifest -> per-file sha256 (for SKILL.md integrity + provenance)
            man = json.loads(_get(api_url)) if api_url else {}
            files = (man.get("version") or {}).get("files") or []
            smd = next((f for f in files if (f.get("path") or "").lower() == "skill.md"), None)

            # SKILL.md body from the skill endpoint's description field
            skill = json.loads(_get(f"{_API}/{slug}"))
            body = (skill.get("skill") or {}).get("description") or ""
            if not body:
                print(f"[clawhub] {slug}: no SKILL.md content available, skipping", file=sys.stderr)
                failed += 1
                continue
            data = body.encode("utf-8")
            if smd and smd.get("sha256"):
                got = hashlib.sha256(data).hexdigest()
                if got != smd["sha256"]:
                    print(f"[clawhub] {slug}: SKILL.md sha256 mismatch (got {got[:12]}…, "
                          f"expected {smd['sha256'][:12]}…); writing anyway", file=sys.stderr)

            skill_dir = out / slug
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_bytes(data)
            (skill_dir / "_clawhub_manifest.json").write_text(
                json.dumps(
                    {
                        "slug": slug,
                        "version": version,
                        "source": f"{_API}/{slug}",
                        "version_api": api_url,
                        "license": (man.get("version") or {}).get("license"),
                        "files": files,  # path/size/sha256/contentType (bodies not redistributed)
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            written += 1
            print(f"[clawhub] {written:>4}. {slug} (v{version}) -> {skill_dir}")
        except Exception as e:  # noqa: BLE001 - keep going on any per-skill failure
            failed += 1
            print(f"[clawhub] {slug}: fetch failed ({e})", file=sys.stderr)

    print(f"[clawhub] done: wrote {written} skill(s) to {out} ({failed} failed). "
          f"Only SKILL.md is re-fetchable from the public API; see each "
          f"_clawhub_manifest.json for the full file list.")
