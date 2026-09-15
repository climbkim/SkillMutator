import os
import time
import argparse
from datetime import datetime
from pathlib import Path
import tiktoken
from dotenv import load_dotenv

# .env loading: prefer a .env next to this file, else its parent directory.
_script_dir = Path(__file__).resolve().parent
_env_candidates = [
    _script_dir / ".env",
    _script_dir.parent / ".env",
]
for _env_path in _env_candidates:
    if _env_path.exists():
        load_dotenv(_env_path)
        break
else:
    load_dotenv()  # fallback: cwd

# Max input+output tokens per provider
MAX_TOKENS_PER_REQUEST = 100000
MAX_TOKENS_BY_PROVIDER = {
    "openai":               100000,
    "google":               100000,
    "anthropic":            100000,
    "huggingface":          20000,   # router: Qwen-7B has a 32K context; leave headroom for output
    "huggingface-endpoint": 20000,   # dedicated endpoint: same
}

# Supported providers
SUPPORTED_PROVIDERS = ["openai", "google", "anthropic", "huggingface", "huggingface-endpoint"]

# HuggingFace backend defaults (per-deployer endpoint URL via $HF_ENDPOINT_URL)
HF_ROUTER_BASE_URL   = "https://router.huggingface.co/v1"
HF_ENDPOINT_BASE_URL = os.environ.get(
    "HF_ENDPOINT_URL",
    "https://your-endpoint-id.region.aws.endpoints.huggingface.cloud/v1",
)

# Default model per provider
DEFAULT_MODELS = {
    "openai":                "gpt-5.4-mini",
    "google":                "gemini-2.5-flash-preview-04-17",
    "anthropic":             "claude-sonnet-4-20250514",
    "huggingface":           "Qwen/Qwen2.5-Coder-7B-Instruct:nscale",
    "huggingface-endpoint":  "Qwen/Qwen2.5-Coder-7B-Instruct",
}

# Default reasoning model per provider
DEFAULT_REASONING_MODELS = {
    "openai":                "o3-mini",
    "google":                "gemini-2.5-flash-preview-04-17",
    "anthropic":             "claude-sonnet-4-20250514",
    "huggingface":           "Qwen/Qwen2.5-Coder-7B-Instruct:nscale",
    "huggingface-endpoint":  "Qwen/Qwen2.5-Coder-7B-Instruct",
}

# Generic security-analyst prompt. The structured 4-Phase (P1--P4) prompt used
# by the fine-tuned scanner lives in the sister `skill-scanner-finetune`
# package; this baseline prompt avoids format constraints so a non-fine-tuned
# LLM can produce free-form vulnerability reasoning.
SYSTEM_PROMPT = (
    "You are an expert AI agent security analyst specializing in LLM-powered agent skill security. "
    "Your task is to analyze agent skills — composed of SKILL.md instruction documents and Python helper scripts. "
    "Reason step-by-step, cite specific file locations and code patterns as evidence, "
    "and distinguish what a skill claims to do versus what it actually does."
)

USER_TEMPLATE = "Analyze this agent skill for security vulnerabilities:\n\n{skill_content}"

_LANG_MAP = {"py": "python", "sh": "bash", "md": "markdown",
             "js": "javascript", "ts": "typescript"}


def _render_file(path: str, content: str, base_dir: str = None) -> str:
    """Render a single file as a markdown fenced block."""
    if base_dir:
        try:
            rel = os.path.relpath(path, base_dir).replace(os.sep, "/")
        except ValueError:
            rel = os.path.basename(path)
    else:
        rel = os.path.basename(path)
    ext = os.path.splitext(path)[1].lstrip(".").lower()
    lang = _LANG_MAP.get(ext, "")
    return f"## {rel}\n```{lang}\n{content}\n```"


def create_client(provider: str, base_url: str = None):
    """Build an API client for the requested provider.

    Args:
        provider: LLM provider identifier.
        base_url: Custom OpenAI-compatible endpoint URL. When set,
                  openai/huggingface-endpoint use this URL — handy for
                  connecting to a rented GPU server (e.g. vLLM).
    """
    if provider == "openai":
        from openai import OpenAI
        if base_url:
            # Custom endpoint (a GPU server or other OpenAI-compatible API)
            api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("CUSTOM_API_KEY", "token")
            return OpenAI(api_key=api_key, base_url=base_url)
        return OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    elif provider == "huggingface":
        from openai import OpenAI
        hf_token = os.environ.get("HF_TOKEN")
        if not hf_token:
            raise ValueError("HF_TOKEN is not set. Check your .env file.")
        effective_url = base_url or HF_ROUTER_BASE_URL
        return OpenAI(base_url=effective_url, api_key=hf_token)
    elif provider == "huggingface-endpoint":
        from openai import OpenAI
        hf_token = os.environ.get("HF_TOKEN")
        if not hf_token:
            raise ValueError("HF_TOKEN is not set. Check your .env file.")
        effective_url = base_url or HF_ENDPOINT_BASE_URL  # --base-url takes precedence
        return OpenAI(base_url=effective_url, api_key=hf_token)
    elif provider == "google":
        import google.generativeai as genai
        genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
        return genai
    elif provider == "anthropic":
        import anthropic
        return anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    else:
        raise ValueError(f"Unsupported provider: {provider}. Supported: {SUPPORTED_PROVIDERS}")


def count_tokens(text: str, model_name: str) -> int:
    """Count tokens in `text`."""
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        encoding = tiktoken.get_encoding("o200k_base")
    return len(encoding.encode(text))


def read_skill_files(directory_path: str) -> dict:
    """Walk `directory_path` recursively and load valid file contents."""
    ignore_dirs = {'.git', '__pycache__', 'node_modules', 'venv', '.idea'}
    valid_extensions = {'.py', '.sh', '.md', '.json', '.yaml', '.yml', '.txt', '.js', '.Dockerfile'}

    file_contents = {}

    for root, dirs, files in os.walk(directory_path):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in valid_extensions or file.lower() == 'dockerfile':
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_contents[file_path] = f.read()
                except UnicodeDecodeError:
                    continue
    return file_contents


def _build_messages(file_batch: dict, base_dir: str = None) -> list:
    """Build chat messages for analysis.

    Same system+user format as the prompt used for fine-tuning data
    generation. Calls are batched, so only files in `file_batch` are rendered
    into `skill_content`.
    """
    rendered = [_render_file(p, c, base_dir) for p, c in file_batch.items()]
    skill_content = "\n\n".join(rendered)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_TEMPLATE.format(skill_content=skill_content)},
    ]


def _call_openai(client, model_name: str, messages: list, use_reasoning: bool) -> dict:
    """Call the OpenAI API."""
    try:
        if use_reasoning:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                reasoning_effort="medium"
            )
        else:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.2
            )
    except Exception as e:
        error_msg = str(e)
        if "temperature" in error_msg.lower() and "unsupported" in error_msg.lower():
            print(f"\n    [!] Note: model '{model_name}' does not support temperature; "
                  f"falling back to its default.")
            response = client.chat.completions.create(
                model=model_name,
                messages=messages
            )
        else:
            raise e

    usage = response.usage
    return {
        "content": response.choices[0].message.content,
        "prompt_tokens": usage.prompt_tokens if usage else 0,
        "completion_tokens": usage.completion_tokens if usage else 0,
        "total_tokens": usage.total_tokens if usage else 0,
    }


def _call_google(client, model_name: str, messages: list, use_reasoning: bool) -> dict:
    """Call the Google Gemini API."""
    system_content = next((m["content"] for m in messages if m["role"] == "system"), None)
    user_content = next((m["content"] for m in messages if m["role"] == "user"), "")

    if system_content:
        model = client.GenerativeModel(model_name, system_instruction=system_content)
    else:
        model = client.GenerativeModel(model_name)

    generation_config = {}
    if use_reasoning:
        generation_config["temperature"] = None
    else:
        generation_config["temperature"] = 0.2

    response = model.generate_content(
        user_content,
        generation_config=generation_config if generation_config else None,
    )

    # Extract token usage
    prompt_tokens = 0
    completion_tokens = 0
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        metadata = response.usage_metadata
        prompt_tokens = getattr(metadata, 'prompt_token_count', 0) or 0
        completion_tokens = getattr(metadata, 'candidates_token_count', 0) or 0

    return {
        "content": response.text,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


def _call_anthropic(client, model_name: str, messages: list, use_reasoning: bool) -> dict:
    """Call the Anthropic Claude API."""
    system_content = next((m["content"] for m in messages if m["role"] == "system"), None)
    user_messages = [m for m in messages if m["role"] != "system"]

    kwargs = {
        "model": model_name,
        "max_tokens": 8192,
        "messages": user_messages,
    }
    if system_content:
        kwargs["system"] = system_content

    if use_reasoning:
        # Use extended thinking
        kwargs["temperature"] = 1  # thinking mode requires temperature=1
        kwargs["thinking"] = {
            "type": "enabled",
            "budget_tokens": 4096,
        }
    else:
        kwargs["temperature"] = 0.2

    try:
        response = client.messages.create(**kwargs)
    except TypeError:
        # Some Anthropic SDK versions reject certain sampling kwargs on
        # messages.create (e.g. `temperature`/`thinking`); retry without them.
        for _k in ("temperature", "thinking"):
            kwargs.pop(_k, None)
        response = client.messages.create(**kwargs)

    # Extract only the text, excluding thinking blocks
    content_text = ""
    for block in response.content:
        if block.type == "text":
            content_text += block.text

    usage = response.usage
    prompt_tokens = usage.input_tokens if usage else 0
    completion_tokens = usage.output_tokens if usage else 0

    return {
        "content": content_text,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


def analyze_vulnerabilities(client, provider: str, file_batch: dict, model_name: str, use_reasoning: bool, base_dir: str = None) -> dict:
    """Send `file_batch` to the model; return analysis output, elapsed time, and token usage."""
    messages = _build_messages(file_batch, base_dir)

    start_time = time.time()

    if provider in ("openai", "huggingface", "huggingface-endpoint"):
        result = _call_openai(client, model_name, messages, use_reasoning)
    elif provider == "google":
        result = _call_google(client, model_name, messages, use_reasoning)
    elif provider == "anthropic":
        result = _call_anthropic(client, model_name, messages, use_reasoning)
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    elapsed_time = time.time() - start_time
    result["time_taken"] = elapsed_time
    return result


def evaluate_agent_skills(client, provider: str, target_directory: str, skill_name: str, model_name: str, use_reasoning: bool, output_dir: str = None, max_input_tokens: int = None):
    """Evaluate the whole directory, gather stats, and save the report.

    SKILL.md anchored batching: SKILL.md is included in every batch so that
    scripts are analyzed in the context of the natural-language directives
    even when the input must be split across batches.
    """
    print(f"[*] starting scan of '{target_directory}' "
          f"(provider: {provider}, model: {model_name}, reasoning: {'ON' if use_reasoning else 'OFF'})...")
    files = read_skill_files(target_directory)

    if not files:
        print("[error] no valid files to analyze.")
        return

    max_tokens = max_input_tokens or MAX_TOKENS_BY_PROVIDER.get(provider, MAX_TOKENS_PER_REQUEST)
    # System prompt + user template + chat-template marker overhead
    base_prompt_tokens = (
        count_tokens(SYSTEM_PROMPT, model_name)
        + count_tokens(USER_TEMPLATE.format(skill_content=""), model_name)
        + 64  # headroom for chat-template / role markers
    )

    # -- Separate the SKILL.md anchor -----------------------------------
    anchor_files = {}
    other_files = {}
    for path, content in files.items():
        if os.path.basename(path).lower() == "skill.md":
            anchor_files[path] = content
        else:
            other_files[path] = content

    anchor_tokens = sum(
        count_tokens(_render_file(p, c, target_directory) + "\n\n", model_name)
        for p, c in anchor_files.items()
    )
    available = max_tokens - anchor_tokens - base_prompt_tokens

    # -- Compose batches: each batch = anchor + assigned scripts --------
    batches = []
    current_others = {}
    current_tokens = 0

    for path, content in other_files.items():
        file_text = _render_file(path, content, target_directory) + "\n\n"
        file_tokens = count_tokens(file_text, model_name)

        if current_tokens + file_tokens > available and current_others:
            batches.append({**anchor_files, **current_others})
            current_others = {}
            current_tokens = 0

        current_others[path] = content
        current_tokens += file_tokens

    if current_others or not batches:
        batches.append({**anchor_files, **current_others})

    if len(batches) > 1:
        print(f"[batching] {len(files)} files -> {len(batches)} batches "
              f"(SKILL.md anchored, max_tokens={max_tokens:,})")

    # -- Run batches ----------------------------------------------------
    all_results = []
    total_time = 0.0
    total_prompt_tokens = 0
    total_completion_tokens = 0

    for i, batch in enumerate(batches, 1):
        label = "(last) " if i == len(batches) else ""
        print(f"[in progress] batch #{i}/{len(batches)} {label}analyzing ({len(batch)} files)...")
        result_data = analyze_vulnerabilities(client, provider, batch, model_name, use_reasoning, base_dir=target_directory)

        all_results.append((i, result_data["content"]))
        total_time += result_data["time_taken"]
        total_prompt_tokens += result_data["prompt_tokens"]
        total_completion_tokens += result_data["completion_tokens"]

    # Build the final stats dict
    stats = {
        "time_taken": total_time,
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "total_tokens": total_prompt_tokens + total_completion_tokens
    }

    print(f"\n[*] analysis done! (total time: {stats['time_taken']:.2f}s)")
    save_report(provider, skill_name, model_name, use_reasoning, list(files.keys()), all_results, stats, output_dir)


def save_report(provider: str, skill_name: str, model_name: str, use_reasoning: bool, scanned_files: list, results: list, stats: dict, output_dir: str = None):
    """Save the analysis output and performance stats to a markdown file."""
    log_dir = output_dir if output_dir else os.path.join(os.getcwd(), "logs")
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    reasoning_str = "Reasoning-ON" if use_reasoning else "Reasoning-OFF"
    safe_skill_name = skill_name.replace("\\", "_").replace("/", "_").replace(":", "_").replace(" ", "_")
    safe_model_name = model_name.replace("\\", "_").replace("/", "_").replace(":", "-").replace(" ", "_")

    filename = f"{safe_skill_name}_{provider}_{safe_model_name}_{reasoning_str}_{timestamp}.md"
    filepath = os.path.join(log_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("# Agent Skill Vulnerability Report\n\n")
        f.write("## Metadata & Performance\n")
        f.write(f"- **Target Skill:** `{skill_name}`\n")
        f.write(f"- **Provider:** `{provider}`\n")
        f.write(f"- **Model Used:** `{model_name}`\n")
        f.write(f"- **Reasoning:** `{'Enabled' if use_reasoning else 'Disabled'}`\n")
        f.write(f"- **Scan Date:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n")
        f.write(f"- **Total Time Taken:** `{stats['time_taken']:.2f} seconds`\n")
        f.write("- **Token Usage:**\n")
        f.write(f"  - Prompt Tokens (input): `{stats['prompt_tokens']:,}`\n")
        f.write(f"  - Completion Tokens (output): `{stats['completion_tokens']:,}`\n")
        f.write(f"  - Total Tokens: `{stats['total_tokens']:,}`\n")
        f.write(f"- **Total Files Scanned:** `{len(scanned_files)}`\n\n")

        f.write("### Scanned Files\n")
        for file in scanned_files:
            relative_path = file.split(skill_name)[-1] if skill_name in file else file
            f.write(f"- `{relative_path}`\n")

        f.write("\n---\n\n## Analysis Results\n\n")

        for batch_num, content in results:
            f.write(f"### Batch #{batch_num}\n\n")
            f.write(content)
            f.write("\n\n---\n\n")

    print(f"[ok] report saved: {filepath}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent Skill Vulnerability Scanner Framework")
    parser.add_argument("-s", "--skill", type=str, help="Agent-skill folder to analyze")
    parser.add_argument("-p", "--provider", type=str, choices=SUPPORTED_PROVIDERS,
                        help="LLM provider (openai, google, anthropic, huggingface, huggingface-endpoint)")
    parser.add_argument("-m", "--model", type=str,
                        help="Model name (defaults to the provider's default model when unspecified)")
    parser.add_argument("-r", "--reasoning", action="store_true",
                        help="Use the provider's reasoning-tier model variant")
    parser.add_argument("-o", "--output-dir", type=str, default=None,
                        help="Report output directory (defaults to logs/)")
    parser.add_argument("-u", "--base-url", type=str, default=None,
                        help="Custom OpenAI-compatible endpoint URL (e.g. a GPU server "
                             "http://host:8000/v1). Used by openai/huggingface-endpoint "
                             "instead of the default URL.")
    parser.add_argument("-t", "--max-tokens", type=int, default=None,
                        help="Input-token cap (defaults to the provider's value). "
                             "vLLM Qwen-7B: 20000 recommended.")

    args = parser.parse_args()
    use_reasoning = args.reasoning

    # Provider config
    provider = args.provider
    if not provider:
        print("-" * 50)
        print(f"[?] Choose an LLM provider: {SUPPORTED_PROVIDERS}")
        provider = input("    > ").strip().lower()
        if provider not in SUPPORTED_PROVIDERS:
            print(f"[error] Unsupported provider: {provider}")
            exit(1)

    # Model config
    if args.model:
        model_name = args.model
    else:
        model_name = DEFAULT_REASONING_MODELS[provider] if use_reasoning else DEFAULT_MODELS[provider]

    # Skill-folder config
    skill_name = args.skill
    if not skill_name:
        print("-" * 50)
        skill_name = input("[?] Enter the agent-skill folder to analyze: ").strip()

    # If an explicit path was given, use it as-is; otherwise resolve under skills/.
    if os.path.isabs(skill_name) or (os.path.sep in skill_name) or ("/" in skill_name):
        target_directory = skill_name
        display_name = os.path.basename(skill_name.rstrip("/\\"))
    else:
        base_path = os.path.join(os.getcwd(), "skills")
        target_directory = os.path.join(base_path, skill_name)
        display_name = skill_name

    print("-" * 50)
    if not skill_name:
        print("[error] no folder name provided.")
    elif os.path.isdir(target_directory):
        client = create_client(provider, base_url=args.base_url)
        evaluate_agent_skills(client, provider, target_directory, display_name, model_name, use_reasoning, args.output_dir, max_input_tokens=args.max_tokens)
    else:
        print(f"\n[error] Path not found: {target_directory}")
