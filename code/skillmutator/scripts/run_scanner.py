"""run_scanner.py -- thin CLI wrapper around the bundled scanners.

This is a convenience entry point that dispatches to one of the three
scanners shipped under `src/skill_mutator/scanners/`. For the LLM scanner
this is functionally identical to invoking `python -m
skill_mutator.scanners.llm_scanner.scanner` directly; the rule-based and
commercial scanners are launched the same way.

Usage:
    # Rule-based SAST
    python scripts/run_scanner.py path/to/skill --scanner skill-security

    # Commercial SCA
    python scripts/run_scanner.py path/to/skill --scanner snyk

    # LLM-based (default model = gpt-5.4-mini; override with -m)
    python scripts/run_scanner.py path/to/skill --scanner llm \\
        --provider openai --model gpt-5.4-mini

    # LLM-based against any OpenAI-compatible endpoint (e.g. self-hosted vLLM)
    python scripts/run_scanner.py path/to/skill --scanner llm \\
        --provider openai --base-url http://localhost:8000/v1 \\
        --model my-finetuned-scanner
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _scanners_root() -> Path:
    here = Path(__file__).resolve().parent.parent
    return here / "src" / "skill_mutator" / "scanners"


def main() -> int:
    ap = argparse.ArgumentParser(description="Run a skill scanner against a skill folder.")
    ap.add_argument("skill_path", help="Path to a skill folder (must contain SKILL.md).")
    ap.add_argument("--scanner", choices=["llm", "skill-security", "snyk"], default="llm",
                    help="Which scanner to invoke.")
    # LLM-scanner-only flags (ignored by the others):
    ap.add_argument("-p", "--provider", default="openai",
                    help="LLM provider (openai/anthropic/google/huggingface). Default: openai.")
    ap.add_argument("-m", "--model", default=None,
                    help="Model id. Defaults to the provider's default in scanner.py.")
    ap.add_argument("-u", "--base-url", default=None,
                    help="OpenAI-compatible endpoint URL (for self-hosted models).")
    ap.add_argument("-o", "--output-dir", default=None,
                    help="Where to write the scan report. Defaults to ./logs/.")
    ap.add_argument("-t", "--max-tokens", type=int, default=None,
                    help="Override the per-call token cap (provider default otherwise).")
    ap.add_argument("-r", "--reasoning", action="store_true",
                    help="Use the provider's reasoning-tier model variant.")
    args = ap.parse_args()

    if args.scanner == "llm":
        scanner_py = _scanners_root() / "llm_scanner" / "scanner.py"
        cmd = [sys.executable, str(scanner_py),
               "-p", args.provider,
               "-s", str(Path(args.skill_path).resolve())]
        if args.model:      cmd += ["-m", args.model]
        if args.base_url:   cmd += ["-u", args.base_url]
        if args.output_dir: cmd += ["-o", args.output_dir]
        if args.max_tokens: cmd += ["-t", str(args.max_tokens)]
        if args.reasoning:  cmd += ["-r"]
    elif args.scanner == "skill-security":
        # `skill-security-scan` PyPI package (installed by install.sh --generate).
        # A local source checkout at scanners/skill_security/ takes precedence.
        # The wheel omits its default config/rules.yaml, so pass --rules when a rules
        # file is available: $SKILL_SECURITY_RULES, else the copy install.sh fetched.
        rules = os.environ.get("SKILL_SECURITY_RULES", "")
        if not rules:
            _cand = Path.home() / ".cache" / "skillmutator" / "skill_security_rules.yaml"
            if _cand.is_file():
                rules = str(_cand)
        extra = ["--rules", rules] if rules else []
        scanner_dir = _scanners_root() / "skill_security"
        if scanner_dir.is_dir():
            cmd = [sys.executable, "-m", "src.cli", "scan", str(Path(args.skill_path).resolve()), *extra]
            return subprocess.run(cmd, cwd=str(scanner_dir)).returncode
        cmd = ["skill-security-scan", "scan", str(Path(args.skill_path).resolve()), *extra]
        try:
            return subprocess.run(cmd).returncode
        except FileNotFoundError:
            print("skill-security-scan not installed; `pip install skill-security-scan` "
                  "(or ./install.sh --generate).", file=sys.stderr)
            return 127
    elif args.scanner == "snyk":
        # `snyk-agent-scan` PyPI package (installed by install.sh --generate).
        # A local source checkout at scanners/snyk_agent/src/ takes precedence.
        cmd = [sys.executable, "-m", "agent_scan.run",
               "--skills", str(Path(args.skill_path).resolve())]
        env = os.environ.copy()
        snyk_src = _scanners_root() / "snyk_agent" / "src"
        if snyk_src.is_dir():
            env["PYTHONPATH"] = str(snyk_src) + os.pathsep + env.get("PYTHONPATH", "")
        return subprocess.run(cmd, env=env).returncode
    else:
        ap.error(f"unknown scanner: {args.scanner}")
        return 2

    return subprocess.run(cmd).returncode


if __name__ == "__main__":
    sys.exit(main())