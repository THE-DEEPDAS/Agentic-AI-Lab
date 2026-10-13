# RP2: Effect of tool-count context on MCP tool selection

AI465 Agentic AI, SVNIT Surat, Semester VII. Research Project Phase 2. Roll no. U23AI052 (individual work).

**Question.** On a 200-task subset of MCPToolBench++ (search, map, finance), how do tool-selection accuracy,
cost and failure composition change when the model sees 5, 20 or 50 tools, with everything else held fixed?

## Status (read this first)

| Item | State |
|---|---|
| Code, data subset, prompts, tests, report and slide generators | complete, 59 tests pass |
| Pipeline tested end to end with an offline mock model (4,200 jobs) | done, output in `results/mock_smoke/`, stamped **MOCK - NOT A RESULT** |
| Run against a real model | **not done**: needs your API key and the exact model version, see "Run it" |
| Numbers in report/slides | none until the real run; `report/RP2_report.pdf` and `slides/RP2_slides.pptx` say "pending" where results go |
| 20-task audit of the scorer against your own labels | **not done**: needs you, see "Audit" |

`report/*_MOCK_PREVIEW.pdf` and `slides/*_MOCK_PREVIEW.pptx` exist only to show the final layout. Do not submit them.

## Declared deviations from the approved objective

1. **Single-step tasks only.** The public release has no multi-step items for search/finance and only 2 of 500 for map, so the subset is 200 single-step tasks (67 search, 67 map, 66 finance) and AST DAG accuracy is not reported.
2. **No execution-based Pass@K** (needs live MCP servers and credentials).
3. **Deterministic scorer instead of the benchmark's GPT-4o judge** (`rp2/scoring.py`).
4. **Distractors from an 87-tool pool** (all six benchmark categories) to reach 20 and 50 tools; native lists are 1, 5 or 32 tools. The gold tool and up to 2 labelled similar tools are always present; contexts are nested.
5. A missing required parameter counts as a parameter error (the benchmark judge only checks predicted parameters).

## Environment

Python 3.10+ (developed on 3.13). Tested on Linux.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Required environment variable for real runs: `LLM_API_KEY` (name configurable in `configs/config.yaml` under `model.api_key_env`).
Never commit keys; `.env` is git-ignored. Mock runs need no key and no network.

## Model and pinned configuration

Edit `configs/config.yaml` **once, before the real run**, then change nothing:

| Key | Meaning |
|---|---|
| `model.provider` | `anthropic`, or `openai_compat` (OpenAI, Groq, Gemini's OpenAI-compatible endpoint, Ollama, vLLM, ...) |
| `model.name` | **exact version string** (a dated snapshot id where the provider has one); the runner refuses to start while it is `null` |
| `model.base_url` | for `openai_compat` only (for Ollama e.g. `http://localhost:11434/v1`) |
| `model.temperature`, `model.top_p`, `model.max_tokens` | decoding; defaults 0.7 / 1.0 / 512. The Anthropic adapter does not send `top_p` (newer Claude models reject it together with temperature) and records that |
| seed | provider seed = `1000 + run*100000 + task_index` where the provider supports seeds, otherwise recorded as unsupported |

Each run directory gets `manifest.json` with: model string requested **and** every model string the API returned, decoding settings, dates (UTC), package versions, git commit, SHA-256 of the prompt files and data, and a copy of the config.

Temperature 0.7 is deliberate: at temperature 0 repeated runs are near-identical and the "mean ± SD over 3 runs" would say little about sampling noise.

## Run it

```bash
# 0. optional sanity checks
python -m pytest -q tests                                   # 59 tests, a few seconds
python scripts/run_experiment.py --tiers 1 2 3 --dry-run    # plan + token estimate, calls nothing

# 1. real experiment (resumes if interrupted; rerun the same command)
export LLM_API_KEY=...
python scripts/run_experiment.py --tiers 1 2 3
#    tier 1 = c05, c20, c50 (the objective)    tier 2 = position and padding ablations    tier 3 = matched budget

# 2. every table and figure from the saved traces
python scripts/aggregate.py --run-dir results/<run>

# 3. report (max 4 pages) and slides
python scripts/make_report.py --run-dir results/<run> --out report/RP2_report.pdf
python scripts/make_slides.py --run-dir results/<run> --out slides/RP2_slides.pptx

# or everything in one go
bash scripts/reproduce.sh
```

| Output | Produced by | Command |
|---|---|---|
| `results/<run>/traces/<cond>/run<k>.jsonl` | runner | step 1 |
| `results/<run>/tables.md`, `summary.json`, `per_task.csv` | aggregator | step 2 |
| `fig_accuracy.png`, `fig_cost.png`, `fig_failures.png` | aggregator | step 2 |
| `failure_case.json` (auto-selected traced failure) | aggregator | step 2 |
| `report/RP2_report.pdf`, `slides/RP2_slides.pptx` | generators | step 3 |

Offline rehearsal with the mock model (not a result): `bash scripts/reproduce.sh mock` (about 10 seconds).

### Expected runtime and cost (estimates, `chars/4` for input tokens)

| Scope | Calls | Input tokens |
|---|---|---|
| Tier 1 (c05, c20, c50) x 3 runs | 1,800 | about 8.2 M |
| Tiers 1-3 x 3 runs | 8,400 | about 29.8 M (tier 3 alone is 4,800 calls, 5.7 M tokens) |

Output is about 30-60 tokens per call. Runtime is bounded by your rate limit: roughly `calls / requests-per-second`. At the default 2 requests per second, tier 1 takes about 15 minutes of pacing plus latency; on a free tier limited to 30 requests per minute, tier 1 takes about an hour and tiers 1-3 about 5 hours. Lower `runtime.max_requests_per_second` if you get rate-limit errors. If budget is tight, run tier 1 first (it already answers the objective) and add tiers 2 and 3 afterwards: the same output directory is reused.

Tier 3's `self_consistency_k: 8` was chosen so that the 5-tool baseline spends about as many tokens per task as the 50-tool condition (9.4 K vs 8.8 K estimated). Check the measured ratio in the report and adjust `k` if the real tokenizer disagrees (then rerun tier 3 into a new directory).

## Audit: check the scorer against your own labels (required: at least 20 tasks)

```bash
python scripts/label_audit.py export --run-dir results/<run> --out results/<run>/audit.csv
# open audit.csv, fill human_tool_ok and human_param_ok with 1/0 for each row, judging from the query, gold and prediction
python scripts/label_audit.py score --csv results/<run>/audit.csv      # writes audit_agreement.json
python scripts/make_report.py --run-dir results/<run>                  # report now quotes agreement and kappa
```

If agreement on parameters is low, tighten the rules in `rp2/scoring.py` (documented at the top of that file), rescore from the saved traces (no new API calls, see below), rerun `aggregate.py`, and report the change.

### Rescoring after a scorer change

Traces store the raw model outputs, so scores can be recomputed without new API calls:

```bash
python scripts/rescore.py --run-dir results/<run>
python scripts/aggregate.py --run-dir results/<run>
```

## Repository layout

```
configs/config.yaml        pinned configuration and condition definitions
prompts/                   system.txt, user.txt, filler.txt (every prompt is a file)
data/                      subset_200.json, tool_pool.json (built by scripts/build_subset.py)
rp2/                       context.py (tool-count manipulation), scoring.py (scorer + taxonomy), models.py,
                           runner.py, aggregate.py, report_text.py
scripts/                   run_experiment.py, aggregate.py, demo.py, label_audit.py, make_report.py,
                           make_slides.py, build_subset.py, rescore.py, package.sh, reproduce.sh
tests/test_pipeline.py     59 tests (nested design, prompts identical, oracle = 100%, perturbations, resume, failures)
results/                   one directory per run (traces, manifest, tables, figures)
report/, slides/           deliverables
```

## Design in one paragraph

Per task, the context is the gold tool plus up to 2 labelled similar tools, filled to 5/20/50 tools from one seeded permutation of the 87-tool pool, so 5 is a subset of 20 is a subset of 50 and going up only adds tools. All conditions use the same prompt files. Ablations each isolate one factor: gold tool first/last at 50 tools (position), 5 tools padded with neutral text to the 50-tool length (length vs. number of choices), 5 tools with 8 majority-voted samples (matched token budget). Jobs are interleaved across conditions within each run so any model drift affects all conditions equally. Scores: `tool_ok` (gold or labelled similar tool), `param_ok` (numeric, enum, lat/lon within 0.1, token-F1 >= 0.5 for free text, list set equality), `ast_ok` = both. Nine exclusive failure labels are listed in `rp2/scoring.py`. Statistics: mean ± SD over runs; paired bootstrap over tasks (10,000 resamples, 95% interval).

## Own code vs borrowed

* **Own:** everything under `rp2/`, `scripts/`, `tests/`, `configs/`, `prompts/` (about 2,100 lines of Python).
* **Borrowed:** the benchmark's task data, tool schemas and labels from <https://github.com/mcp-tool-bench/mcptoolbenchpp> at commit `2bd35e58ed5ebe79bbb12df0f9919a34ed2cb037` (copied into `data/` by `scripts/build_subset.py`), and the parameter-matching rules from its judge prompt, which are re-implemented. No benchmark code is imported or run. The borrowed part (data) is not code, and the code is entirely new.

## Known limitations

One model and temperature; single-step tasks only; the benchmark's `similar_tools` list may miss valid alternatives (inflating same-domain "wrong tool" counts); distractors are mostly cross-domain and therefore easier than a real marketplace; parameter matching is lenient, as in the benchmark; the public benchmark may be in the model's training data. These are repeated in the report.
