"""LLM provider factory.

Auto-loads `.env` from the package root (or its parent), resolves a provider
from either an explicit string or a model-name prefix, and returns a
configured BaseLLM instance.
"""
import importlib
import os
from pathlib import Path

from dotenv import load_dotenv

from .base import BaseLLM

# Auto-load .env from the package root or one level above (project root).
_root = Path(__file__).resolve().parent.parent
for _env in (_root / ".env", _root.parent / ".env"):
    if _env.exists():
        load_dotenv(_env)

# HuggingFace backend URLs.
# - Router: shared serverless endpoint (pay-per-token)
# - Endpoint: deployer-specific dedicated endpoint, supplied via $HF_ENDPOINT_URL
_HF_ROUTER_URL   = "https://router.huggingface.co/v1"
_HF_ENDPOINT_URL = os.environ.get(
    "HF_ENDPOINT_URL",
    "https://your-endpoint-id.region.aws.endpoints.huggingface.cloud/v1",
)

PROVIDERS = {
    "openai":               "openai_llm.OpenAILLM",
    "huggingface":          "huggingface_llm.HuggingFaceLLM",
    "hf":                   "huggingface_llm.HuggingFaceLLM",
    # OpenAI-compatible: HuggingFace Router (serverless, pay-per-token)
    "huggingface-router":   "openai_llm.OpenAILLM",
    # OpenAI-compatible: HuggingFace Dedicated Endpoint (per-deployer URL)
    "huggingface-endpoint": "openai_llm.OpenAILLM",
    # Claude via the local Claude Code headless CLI (no ANTHROPIC_API_KEY).
    "claude-code":          "claude_code_llm.ClaudeCodeLLM",
    "claude":               "claude_code_llm.ClaudeCodeLLM",
}

# Auto-detect provider from a model name prefix.
MODEL_PREFIX_MAP = {
    "gpt-": "openai",
    "o1":   "openai",
    "o3":   "openai",
    "text-davinci": "openai",
    "claude-": "claude-code",
}


def create_llm(provider: str | None = None, model_name: str = "", **kwargs) -> BaseLLM:
    """Factory for BaseLLM instances.

    Args:
        provider:   "openai" or "huggingface"/"hf". When None, the provider is
                    auto-detected from `model_name`.
        model_name: model identifier (e.g. "gpt-4o", "Qwen/Qwen2.5-Coder-7B-Instruct").
        **kwargs:   extra arguments forwarded to the LLM constructor.

    Returns:
        A BaseLLM instance.

    Examples:
        >>> llm = create_llm("openai", model_name="gpt-4o")
        >>> llm = create_llm(model_name="gpt-4o-mini")  # auto-detects "openai"
        >>> llm = create_llm("huggingface", model_name="mistralai/Mistral-7B-Instruct-v0.2")
    """
    if provider is None:
        provider = _detect_provider(model_name)

    provider_key = provider.lower()
    if provider_key not in PROVIDERS:
        raise ValueError(
            f"Unsupported provider: '{provider}'. "
            f"Available: {list(PROVIDERS.keys())}"
        )

    module_path, class_name = PROVIDERS[provider_key].rsplit(".", 1)

    module = importlib.import_module(f".{module_path}", package=__package__)
    cls = getattr(module, class_name)

    # HuggingFace OpenAI-compatible backends: inject base_url and api_key.
    if provider_key == "huggingface-router":
        kwargs.setdefault("base_url", _HF_ROUTER_URL)
        kwargs.setdefault("api_key", os.getenv("HF_TOKEN"))
    elif provider_key == "huggingface-endpoint":
        kwargs.setdefault("base_url", _HF_ENDPOINT_URL)
        kwargs.setdefault("api_key", os.getenv("HF_TOKEN"))

    return cls(model_name=model_name, **kwargs)


def _detect_provider(model_name: str) -> str:
    for prefix, provider in MODEL_PREFIX_MAP.items():
        if model_name.startswith(prefix):
            return provider
    # Fall back to HuggingFace when the name looks like 'org/model'.
    if "/" in model_name:
        return "huggingface"
    raise ValueError(
        f"Cannot auto-detect provider for model name '{model_name}'. "
        "Pass `provider=...` explicitly."
    )
