"""
scan.py - security scan CLI unified runner

Usage:
    python scan.py calculator                                   # scan skills/calculator with the default scanners (snyk, skill-security)
    python scan.py calculator --scanner snyk                    # snyk only
    python scan.py calculator --scanner skill-security          # skill-security-scan only
    python scan.py calculator --scanner llm                     # LLM scanner (.env default)
    python scan.py calculator --scanner llm --provider anthropic --reasoning  # LLM option set
    python scan.py calculator --all                             # run every scanner including the LLM

Log paths:
    --log-dir   <given-path>/<scanner>/<YY-MM-DD-HH-MM>_<folder-name>.log
    mutation scan:  result/.../iter_N/logs/<scanner>/...
    baseline scan:  baseline_result/<skill>/<scanner>/...
"""

import argparse
import io
import os
import subprocess
import sys
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env (SNYK_TOKEN, LLM config, etc.)
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

# Ensure UTF-8 output on the Windows console
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

_PKG_DIR     = Path(__file__).resolve().parent          # src/skill_mutator (this package)
BASE_DIR     = _PKG_DIR.parent.parent                   # repo root
SKILLS_DIR   = BASE_DIR / "skills"
# The bundled scanners live inside this package (src/skill_mutator/scanners/),
# NOT at the repo root — resolve them from the package dir, not BASE_DIR.
SCANNERS_DIR = _PKG_DIR / "scanners"
def get_default_log_dir():
    return BASE_DIR / "log"

LOG_DIR = get_default_log_dir()


# ── Scanner registry ────────────────────────────────────────────────

_SCANNERS: dict[str, type["BaseScanner"]] = {}

# scanners excluded from the default run (API cost, etc.)
_OPTIONAL_SCANNERS: set[str] = set()


def register(name: str, *, optional: bool = False):
    """Decorator that registers a scanner class by its name.
    When optional=True, the scanner runs only with explicit --scanner or with --all."""
    def decorator(cls):
        _SCANNERS[name] = cls
        if optional:
            _OPTIONAL_SCANNERS.add(name)
        return cls
    return decorator



class BaseScanner(ABC):
    """To add a new scanner, subclass this class and register it with @register."""

    def __init__(self, folder: str, log_dir: Path = None):
        self.folder = folder
        skills_path = Path(folder)
        if skills_path.is_absolute() and skills_path.exists():
            self.skills_path = skills_path
        else:
            self.skills_path = SKILLS_DIR / folder
        self.log_dir = log_dir if log_dir is not None else get_default_log_dir()

    @property
    @abstractmethod
    def scanner_name(self) -> str:
        """Scanner name used as the log subdirectory."""

    @abstractmethod
    def build_command(self) -> list[str]:
        """Return the CLI command list to run."""

    def validate(self):
        """Validate before running; SystemExit on problem."""
        if not self.skills_path.exists():
            print(f"error: skills folder does not exist: {self.skills_path}")
            sys.exit(1)

    def log_path(self) -> Path:
        timestamp = datetime.now().strftime("%y-%m-%d-%H-%M")
        folder_name = Path(self.folder).name
        # self.log_dir is the direct parent for logs (caller sets iter_N/logs or baseline/skill)
        log_dir = self.log_dir / self.scanner_name
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / f"{timestamp}_{folder_name}.log"

    def run(self) -> int:
        self.validate()
        cmd = self.build_command()
        dest = self.log_path()

        print(f"[scan] target: {self.skills_path}")
        print(f"[scan] command: {' '.join(cmd)}")
        print(f"[scan] log: {dest}")

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", env=env,
        )

        with open(dest, "w", encoding="utf-8") as f:
            if result.stdout:
                f.write(result.stdout)
            if result.stderr:
                f.write("\n--- stderr ---\n")
                f.write(result.stderr)

        # also print to the terminal
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        print(f"[scan] done (exit {result.returncode}) → {dest}")
        return result.returncode


# -- scanner implementations -----------------------------------------

@register("snyk")
class SnykAgentScanner(BaseScanner):
    scanner_name = "snyk-agent-scan"

    def build_command(self) -> list[str]:
        return [
            sys.executable, "-m", "agent_scan.run",
            "--skills", str(self.skills_path),
        ]

    def run(self) -> int:
        self.validate()
        cmd = self.build_command()
        dest = self.log_path()
        # The Snyk Agent scanner is the PyPI package `snyk-agent-scan`
        # (installed by `install.sh --generate`); `python -m agent_scan.run`
        # resolves it from the environment. For a source checkout placed at
        # scanners/snyk_agent/, prepend its src/ so the local copy wins.
        snyk_src = SCANNERS_DIR / "snyk_agent" / "src"

        print(f"[scan] target: {self.skills_path}")
        print(f"[scan] command: {' '.join(cmd)}")
        print(f"[scan] log: {dest}")

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        if snyk_src.is_dir():
            env["PYTHONPATH"] = str(snyk_src) + os.pathsep + env.get("PYTHONPATH", "")
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            env=env,
        )

        with open(dest, "w", encoding="utf-8") as f:
            if result.stdout:
                f.write(result.stdout)
            if result.stderr:
                f.write("\n--- stderr ---\n")
                f.write(result.stderr)

        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        print(f"[scan] done (exit {result.returncode}) → {dest}")
        return result.returncode


@register("skill-security")
class SkillSecurityScanner(BaseScanner):
    scanner_name = "skill-security-scan"

    def build_command(self) -> list[str]:
        # skill-security-scan is the third-party MIT package `skill-security-scan`
        # (installed by `install.sh --generate`), NOT vendored. If a source
        # checkout is placed at scanners/skill_security/, run it in-place;
        # otherwise use the pip-installed `skill-security-scan` console script.
        #
        # The PyPI wheel (1.0.0) omits its default `config/rules.yaml`, so pass
        # `--rules` to a rules file when one is available: $SKILL_SECURITY_RULES,
        # else the copy `install.sh --generate` fetches from the tool's repo.
        # Without a rules file the tool errors and this scanner column is skipped.
        rules = os.environ.get("SKILL_SECURITY_RULES", "")
        if not rules:
            cand = Path.home() / ".cache" / "skillmutator" / "skill_security_rules.yaml"
            if cand.is_file():
                rules = str(cand)
        extra = ["--rules", rules] if rules else []
        if (SCANNERS_DIR / "skill_security").is_dir():
            return [sys.executable, "-m", "src.cli",
                    "scan", str(self.skills_path), "--format", "console", *extra]
        return ["skill-security-scan", "scan", str(self.skills_path), "--format", "console", *extra]

    def run(self) -> int:
        self.validate()
        cmd = self.build_command()
        dest = self.log_path()
        scanner_dir = SCANNERS_DIR / "skill_security"
        cwd = str(scanner_dir) if scanner_dir.is_dir() else None

        print(f"[scan] target: {self.skills_path}")
        print(f"[scan] command: {' '.join(cmd)}")
        print(f"[scan] log: {dest}")

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8",
                env=env, cwd=cwd,
            )
        except FileNotFoundError:
            msg = ("skill-security-scan not installed. Install it with "
                   "`pip install skill-security-scan` (or `./install.sh --generate`), "
                   "or place a source checkout of github.com/huifer/skill-security-scan "
                   "at scanners/skill_security/. Skipping this scanner.")
            print(f"[scan] {msg}", file=sys.stderr)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(msg + "\n", encoding="utf-8")
            return 127

        with open(dest, "w", encoding="utf-8") as f:
            if result.stdout:
                f.write(result.stdout)
            if result.stderr:
                f.write("\n--- stderr ---\n")
                f.write(result.stderr)

        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        print(f"[scan] done (exit {result.returncode}) → {dest}")
        return result.returncode


@register("llm", optional=True)
class LLMScanner(BaseScanner):
    scanner_name = "llm-scanner"

    # Options injected by the CLI (configured in main).
    provider: str = ""
    model: str = ""
    reasoning: bool = False

    def build_command(self) -> list[str]:
        provider = self.provider or os.getenv("LLM_PROVIDER", "openai")
        model = self.model or os.getenv("LLM_MODEL", "")
        reasoning = self.reasoning or os.getenv("LLM_REASONING", "false").lower() == "true"

        # report path: like log_path(), self.log_dir / scanner_name
        report_dir = self.log_dir / self.scanner_name
        report_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            sys.executable,
            str(SCANNERS_DIR / "llm_scanner" / "scanner.py"),
            "-p", provider,
            "-s", self.folder,
            "-o", str(report_dir),
        ]
        if model:
            cmd.extend(["-m", model])
        if reasoning:
            cmd.append("-r")
        return cmd

    def run(self) -> int:
        self.validate()
        cmd = self.build_command()
        dest = self.log_path()

        print(f"[scan] target: {self.skills_path}")
        print(f"[scan] command: {' '.join(cmd)}")
        print(f"[scan] log: {dest}")

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        # the LLM-scanner resolves skills/ from cwd, so set the project root as cwd
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            env=env, cwd=str(BASE_DIR),
        )

        with open(dest, "w", encoding="utf-8") as f:
            if result.stdout:
                f.write(result.stdout)
            if result.stderr:
                f.write("\n--- stderr ---\n")
                f.write(result.stderr)

        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        print(f"[scan] done (exit {result.returncode}) → {dest}")
        return result.returncode


# ── CLI ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="security scan unified runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Usage examples:\n"
            "  python scan.py calculator                          # default scanner(snyk, skill-security)\n"
            "  python scan.py calculator --scanner llm             # LLM scanner (.env default)\n"
            "  python scan.py calculator -s llm --provider anthropic -r  # LLM + option\n"
            "  python scan.py calculator --all                     # run every scanner including the LLM\n"
        ),
    )
    parser.add_argument(
        "folder",
        help="Folder name under skills/, or a skill-directory path",
    )
    parser.add_argument(
        "--log-dir",
        default=None,
        help="Log output path (default: ./log or below result)",
    )
    parser.add_argument(
        "--scanner", "-s",
        choices=sorted(_SCANNERS.keys()),
        default=None,
        help="Scanner to use (when unspecified, only default scanners run; llm excluded)",
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        dest="run_all",
        help="Run every scanner including the LLM scanner",
    )

    # LLM scanner option
    llm_group = parser.add_argument_group("LLM scanner options (used with --scanner llm)")
    llm_group.add_argument(
        "--provider",
        choices=["openai", "google", "anthropic"],
        default=None,
        help="LLM provider (when unspecified, uses LLM_PROVIDER from .env)",
    )
    llm_group.add_argument(
        "--model",
        default=None,
        help="LLM model name (when unspecified Default model per provider)",
    )
    llm_group.add_argument(
        "--reasoning", "-r",
        action="store_true",
        help="Enable reasoning mode",
    )

    args = parser.parse_args()

    # Decide which scanners to run
    if args.scanner:
        scanners_to_run = [args.scanner]
    elif args.run_all:
        scanners_to_run = sorted(_SCANNERS.keys())
    else:
        # default: exclude optional scanners
        scanners_to_run = sorted(k for k in _SCANNERS if k not in _OPTIONAL_SCANNERS)

    # log_dir process
    log_dir = Path(args.log_dir) if args.log_dir else get_default_log_dir()

    exit_code = 0
    for name in scanners_to_run:
        scanner_cls = _SCANNERS[name]
        scanner = scanner_cls(args.folder, log_dir=log_dir)

        # Inject CLI options into the LLM scanner
        if isinstance(scanner, LLMScanner):
            if args.provider:
                scanner.provider = args.provider
            if args.model:
                scanner.model = args.model
            scanner.reasoning = args.reasoning

        ret = scanner.run()
        if ret != 0:
            exit_code = ret

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
