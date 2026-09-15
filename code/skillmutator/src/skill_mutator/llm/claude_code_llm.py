"""claude_code_llm.py -- Claude Code CLI (headless) as an LLM backend.

Routes LLM calls through the local ``claude -p`` headless CLI instead of the
Anthropic API, so no ANTHROPIC_API_KEY is required (it uses Claude Code's own
authentication). Added so SkillMutator can run Claude (Opus) as an adversarial
oracle alongside the GPT-family oracles.

Caveat: ``claude -p`` is an agent session, not a raw API completion. To keep
behaviour close to a single-shot completion, tools are disabled
(``--allowedTools ""``) and each call runs in a neutral temp directory so a
project-level CLAUDE.md is not picked up.
"""
import glob
import os
import subprocess
import tempfile
from typing import Any

from .base import BaseLLM


def _discover_claude_bin() -> str | None:
    """Locate the Claude Code native binary.

    Resolution order: ``$CLAUDE_CODE_BIN`` -> PATH -> the VSCode extension
    install (newest version wins).
    """
    env_bin = os.environ.get("CLAUDE_CODE_BIN")
    if env_bin and os.path.exists(env_bin):
        return env_bin

    from shutil import which
    on_path = which("claude")
    if on_path:
        return on_path

    home = os.path.expanduser("~")
    pattern = os.path.join(
        home, ".vscode", "extensions",
        "anthropic.claude-code-*", "resources", "native-binary", "claude.exe",
    )
    matches = sorted(glob.glob(pattern))
    return matches[-1] if matches else None


class ClaudeCodeLLM(BaseLLM):
    """Wraps the Claude Code CLI (``claude -p``) as a completion endpoint.

    Each call spawns a fresh headless ``claude -p`` process with all tools
    disabled, feeding the prompt over stdin (mutation prompts can reach tens of
    thousands of characters, well beyond Windows command-line limits).
    """

    def __init__(
        self,
        model_name: str = "claude-opus-4-7",
        claude_bin: str | None = None,
        timeout: int = 900,
        **kwargs,
    ):
        super().__init__(model_name, **kwargs)
        self.claude_bin = claude_bin or _discover_claude_bin()
        self.timeout = timeout
        if not self.claude_bin or not os.path.exists(self.claude_bin):
            raise FileNotFoundError(
                "Claude Code binary not found. Set $CLAUDE_CODE_BIN to the "
                "absolute path of claude.exe."
            )

    def call(self, prompt: str, **kwargs) -> str:
        """Single-prompt call."""
        return self._run(prompt)

    def chat(self, messages: list[dict], **kwargs) -> str:
        """Flatten a messages list into one prompt; system role is forwarded
        via --append-system-prompt."""
        system_parts, convo = [], []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_parts.append(content)
            else:
                tag = "User" if role == "user" else "Assistant"
                convo.append(f"{tag}: {content}")
        system = "\n\n".join(system_parts) or None
        return self._run("\n\n".join(convo), system=system)

    def _run(self, prompt: str, system: str | None = None) -> str:
        cmd = [
            self.claude_bin, "-p",
            "--model", self.model_name,
            "--allowedTools", "",   # disable tools -> single-shot completion
        ]
        if system:
            cmd += ["--append-system-prompt", system]
        try:
            proc = subprocess.run(
                cmd,
                input=prompt.replace("\x00", ""),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
                cwd=tempfile.gettempdir(),  # neutral cwd: skip project CLAUDE.md
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"claude -p timed out after {self.timeout}s "
                f"(model={self.model_name})"
            )
        if proc.returncode != 0:
            raise RuntimeError(
                f"claude -p failed (exit {proc.returncode}): "
                f"{(proc.stderr or '').strip()[:500]}"
            )
        out = (proc.stdout or "").strip()
        if not out:
            raise RuntimeError("claude -p returned empty output")
        return out

    def get_langchain_llm(self) -> Any:
        raise NotImplementedError(
            "ClaudeCodeLLM has no LangChain adapter; the SkillMutator "
            "mutation pipeline calls .call()/.chat() directly."
        )
