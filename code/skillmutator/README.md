# skill-mutator

> Adversarial mutation framework and multi-scanner evaluation harness for LLM agent skills.

`skill-mutator` produces adversarially mutated SKILL.md+code skills, runs a suite
of scanners against them (rule-based, commercial, and LLM-based), and aggregates
the results into a cross-model detection-rate matrix.

The fine-tuning side — taking the mutated benchmark and distilling a 7B-class
local scanner from it — lives in the sister package
[`skill-scanner-finetune`](https://github.com/climbkim/SkillMutator).

## Features

- **Mutation pipeline** — for each target skill, selects context-plausible
  attack categories (13 total), generates per-category attack scenarios, and
  emits mutated SKILL.md + helper script files.
- **Iterative Evasion Refinement** — feeds scanner detections back to the
  mutator LLM to produce stealthier variants across multiple iterations.
- **Multi-scanner harness** — wraps three rule-based / commercial / LLM
  scanners behind a common interface; results are diffed against a clean
  baseline scan of the unmutated skill.
- **Multi-provider LLM clients** — OpenAI, Anthropic, Google, and HuggingFace
  inference are all supported via a single `create_llm(...)` factory.
- **Community-skill crawler** — `scripts/crawl_skills.py` (and
  `run.sh --crawl --registry {anthropic,clawhub}`) assembles an evaluation
  corpus: `anthropic` clones the 17 published paper skills; `clawhub` fetches
  SKILL.md from the ClawHub API via a manifest CSV. No skill bodies are
  redistributed — the backends re-fetch from the public sources.

## Install

```bash
git clone https://github.com/climbkim/SkillMutator.git
cd skill-mutator
pip install -e .[all]
cp .env.example .env   # then fill in OPENAI_API_KEY (and optionally HF_TOKEN, SNYK_TOKEN, ...)
```

Requirements: Python 3.10+, plus an API key for whichever provider you use as
the mutator/scanner backend.

The `snyk` scanner is the third-party `snyk-agent-scan` package (Apache-2.0,
**not** vendored); `pip install -e .[all]` (or `.[scan]`) pulls it in, and it
needs a `SNYK_TOKEN` at run time. Without it the Snyk column is simply left
unavailable — the LLM scanner and `skill-security` still run.

## Quickstart

```bash
# Run the smoke test (no API calls).
python -m pytest tests/test_smoke.py -v

# Mutate one skill with GPT-5.4-mini as the adversarial oracle.
python scripts/run_mutation.py path/to/skill \
       --provider openai --model gpt-5.4-mini --max-iters 5

# Run a single scanner against a (possibly mutated) skill.
python scripts/run_scanner.py path/to/skill --scanner llm

# Sweep many skills at once (mutates every skill folder under ./skills).
python scripts/run_all_skills.py --provider openai
```

Mutation outputs land at
`./results/<skill_name>/<timestamp>_<mode>/generate_skill/<attack_category>/iter_K/`
with one mutated `SKILL.md` (and any modified helper scripts) per attack
category per iteration, plus per-scanner reports and a top-level comparison CSV.

## Configuration

| Env var          | Purpose                                                 |
|------------------|---------------------------------------------------------|
| `OPENAI_API_KEY` | OpenAI mutator / OpenAI LLM scanner                     |
| `ANTHROPIC_API_KEY` | Anthropic mutator / Claude LLM scanner               |
| `GOOGLE_API_KEY` | Google mutator                                          |
| `HF_TOKEN`       | HuggingFace model downloads                             |
| `SNYK_TOKEN`     | Snyk Agent Scan API access                              |

Copy `.env.example` to `.env` and fill in only the providers you intend to
use; the others can be left blank.

## Project layout

```
skill-mutator/
├── src/skill_mutator/
│   ├── process/             # mutation + evasion refinement + scan comparison
│   ├── llm/                 # OpenAI / Anthropic / Google / HuggingFace clients
│   ├── scanners/
│   │   └── llm_scanner/     # LLM-based semantic scanner (ours, MIT)
│   │                        # skill-security-scan (MIT) & Snyk (Apache-2.0):
│   │                        # third-party, pip-installed (in requirements.txt; not vendored)
│   ├── crawler/             # skill-corpus crawler backends (anthropic, clawhub)
│   └── utils/
├── examples/skills/         # bundled sample skill for the demo/smoke test
├── skills/                  # default skill pool (empty; drop skills here)
├── scripts/                 # CLI entry points (run_mutation, run_scanner, crawl_skills, …)
├── docs/                    # ARCHITECTURE, USAGE, attack_categories.json
└── tests/
```

## Attack categories

Mutations are drawn from a 13-category taxonomy spanning data exfiltration,
information gathering, privilege escalation, configuration weakening,
supply-chain attack, brand hijacking, and others. Full list in
[`docs/attack_categories.json`](docs/attack_categories.json). The pipeline
diagram is in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## License

MIT. See [LICENSE](LICENSE).

## Citation

If you use this codebase, please cite the accompanying paper:

```bibtex
@inproceedings{skillmutator2026,
  title  = {<paper title — to fill in>},
  author = {<authors — anonymized>},
  year   = {2026},
}
```
