# LLM-Scanner

A semantic security scanner for LLM Agent Skills that uses large language models to identify vulnerabilities that rule-based tools miss.

## Supported Providers

| Provider | Key | Models |
|----------|-----|--------|
| OpenAI | `openai` | `gpt-4o-mini`, `gpt-4o`, `gpt-5.4-mini`, ... |
| Anthropic | `anthropic` | `claude-sonnet-*`, `claude-opus-*` |
| Google | `google` | `gemini-2.0-flash`, ... |
| HuggingFace Router | `huggingface` | `Qwen/Qwen2.5-Coder-7B-Instruct:nscale` |
| HuggingFace Endpoint | `huggingface-endpoint` | `Qwen/Qwen2.5-Coder-7B-Instruct` |

## Setup

```bash
cp .env.example .env
# Add your API keys
```

## Usage

```bash
# Scan a skill directory with GPT-4o-mini
python scanner.py -p openai -m gpt-4o-mini -s path/to/skill/

# Scan with Qwen-7B via HuggingFace endpoint
python scanner.py -p huggingface-endpoint -m Qwen/Qwen2.5-Coder-7B-Instruct -s path/to/skill/

# Enable reasoning mode
python scanner.py -p openai -m gpt-4o-mini -s path/to/skill/ --reasoning

# Specify output directory
python scanner.py -p openai -m gpt-4o-mini -s path/to/skill/ -o output/logs/
```

## Token Limits by Provider

| Provider | Max Tokens per Batch |
|----------|---------------------|
| OpenAI | 100,000 |
| Anthropic | 100,000 |
| Google | 100,000 |
| HuggingFace (any) | 20,000 |

Large skill directories are automatically chunked into batches within these limits.
