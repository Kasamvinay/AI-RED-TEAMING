# Autonomous AI Red Teaming Framework

An extensible framework that automatically red-teams AI-powered applications
before deployment: it generates adversarial prompts, sends them to a target
system, evaluates the responses for safety violations, learns from the
results, and produces a structured vulnerability report.

Built for AI Engineers, AI QA teams, and AI Security teams who need
repeatable, low-cost safety testing instead of ad-hoc manual prompting.

Primary use case: an **enterprise customer support chatbot**. The same
framework is designed to extend to banking assistants, HR assistants,
internal copilots, and RAG applications without changing the core.

---

## Quickstart

```bash
pip install -r requirements.txt

# Fully offline demo — no API key needed, $0 cost
python main.py --target mock --objective customer_support --max-iterations 15 --max-llm-calls 0

# Real run against an OpenAI-backed target, with a small LLM Analyst budget.
# Set your key once by copying .env.example -> .env and filling it in
# (main.py loads .env automatically). Or export/set it in your shell instead:
#   macOS/Linux:  export OPENAI_API_KEY=sk-...
#   Windows PS:   $env:OPENAI_API_KEY = "sk-..."
#   Windows cmd:  set OPENAI_API_KEY=sk-...
python main.py --target openai --objective customer_support --max-iterations 20 --max-llm-calls 10

# Run it again on the SAME knowledge base and watch it favor strategies
# that worked last time (omit --fresh-kb to keep learning across runs):
python main.py --target openai --objective customer_support --max-iterations 20 --max-llm-calls 10
```

Reports land in `output/reports/<run_name>_<timestamp>.md` (human-readable,
includes a strategy performance / RL policy table) and `.json`
(machine-readable). Every attack/response/analysis is appended to
`output/experience_memory.jsonl`, and the Attack Knowledge Base itself
persists at `output/knowledge_base.sqlite3` — **delete or pass
`--fresh-kb` to reset learning**, otherwise every run builds on the last.

Run the offline test suite:
```bash
python -m pytest tests/ -v
# or, without pytest installed:
python tests/test_autonomous_pipeline_offline.py
python tests/test_pipeline_offline.py
```

> **Note on the legacy pipeline:** the original single-pass pipeline
> (Attack Generator -> Judge -> Memory -> mutation-based Refiner) is still
> present and still works — run it with `python main_legacy.py`. Nothing
> was deleted when the autonomous loop was added; `main.py` now points at
> the newer, learning-capable pipeline by default. See
> [Legacy pipeline](#legacy-pipeline-still-available) below.

---

## Architecture

The framework specializes in **Prompt Injection** (OWASP LLM Top 10 #1)
as its first supported vulnerability class, and runs as a continuous
learning loop rather than a one-shot generate-and-judge pass:

```
Benchmark Dataset
      |
      v
Attack Knowledge Base  <-------------------------------------------+
      |                                                             |
      v                                                             |
Strategy Planner (RL policy: explore vs. exploit)                   |
      |                                                             |
      v                                                             |
Prompt Generator (guided by strategy + KB experience)                |
      |                                                             |
      v                                                             |
Target System Adapter -> Target AI System                            |
      |                                                             |
      v                                                             |
Attack Analyst (Rule-Based -> LLM fallback; structured analysis)     |
      |                                                             |
      v                                                             |
Experience Memory                                                    |
      |                                                             |
      v                                                             |
RL Policy Update  ---------------------------------------------------+
(this update IS a write into the Attack Knowledge Base)
```

Every single attack's outcome feeds straight back into the Knowledge
Base before the next strategy is chosen — that's what makes this
*autonomous learning* rather than *generate once, judge, refine in
bulk*. `core/orchestrator.py::AutonomousOrchestrator` drives this loop,
depending only on the abstract interfaces in `core/interfaces.py`.

### Folder structure

```
core/            Interfaces, shared types, both Orchestrators, both Memory stores.
adapters/        Target System Adapters: mock, OpenAI, generic REST, enterprise chatbot.
knowledge_base/  SQLite-backed Attack Knowledge Base — strategies, variants,
                 experiences, benchmark exemplars. Where the RL policy's state lives.
judge/           RuleBasedJudge/HybridJudge (legacy) + RuleBasedAttackAnalyzer/
                 HybridAttackAnalyst (autonomous pipeline — structured analysis).
attacks/         StrategyPlanner (picks a strategy), PromptGenerator (writes the
                 prompt), policy.py (epsilon-greedy bandit), reward.py, plus the
                 legacy AttackGenerator/MutationAttackRefiner.
benchmarks/      JSON datasets + loader — now used only to bootstrap the
                 Knowledge Base, not replayed directly.
objectives/      YAML profiles defining "safe behavior" per system type.
reporting/       ExperienceReportGenerator (autonomous) + legacy report_generator.
config/          config.yaml + settings loader.
output/          Reports, knowledge_base.sqlite3, experience_memory.jsonl.
tests/           Offline smoke tests for both pipelines (mock adapter, no LLM).
main.py          Autonomous pipeline CLI entry point (the default).
main_legacy.py   Original single-pass pipeline CLI entry point (still works).
```

### Component responsibilities (autonomous pipeline)

| Component | File(s) | LLM calls? |
|---|---|---|
| Attack Knowledge Base | `knowledge_base/attack_knowledge_base.py` | **No.** SQLite reads/writes; also where policy updates land. |
| Strategy Planner | `attacks/strategy_planner.py` + `attacks/policy.py` | **No.** Epsilon-greedy bandit over KB stats. |
| Prompt Generator | `attacks/prompt_generator.py` (`TemplatePromptGenerator`, default) | **No.** Template + goal rotation + variant bandit. An optional `LLMPromptGenerator` exists in the same file but isn't wired in by default. |
| Target System Adapter | `adapters/*.py` | Only the target call itself (unavoidable — that's the system under test) |
| Attack Analyst | `judge/attack_analyst.py` (`RuleBasedAttackAnalyzer` -> `HybridAttackAnalyst`) | Rule-based first; LLM only when confidence is low AND budget remains |
| Experience Memory | `core/memory.py::JsonlExperienceMemory` | **No.** Full audit log of every experience. |
| Report Generator | `reporting/experience_report_generator.py` | **No.** Pure templating; includes strategy performance table. |
| Orchestrator | `core/orchestrator.py::AutonomousOrchestrator` | **No.** Coordination only. |

**Net effect:** for a typical run, the only paid API calls are (a) each
call to the target system being tested, which is inherent to testing it,
and (b) a capped number of Attack Analyst LLM calls, only for responses
the rule-based analyzer genuinely can't classify.

---

## The Target System Adapter contract

Every adapter implements one method:

```python
class TargetSystemAdapter(ABC):
    def send(self, prompt: AttackPrompt) -> TargetResponse: ...
```

Shipped adapters:
- `adapters/mock_adapter.py` — deterministic, offline, zero cost. Use for
  development, CI, and demos.
- `adapters/openai_adapter.py` — wraps an OpenAI chat model.
- `adapters/rest_api_adapter.py` — generic HTTP JSON adapter with
  pluggable request/response shaping; `EnterpriseChatbotAdapter` is a
  semantically-named subclass of it for the primary use case.

To add a new target (Claude, Gemini, a RAG pipeline, an internal
copilot), add one new file in `adapters/` implementing `send()`. Nothing
in `core/`, `judge/`, `attacks/`, or `reporting/` needs to change.

---

## The Attack Knowledge Base

`knowledge_base/attack_knowledge_base.py` (`SQLiteAttackKnowledgeBase`) is
a small SQLite database (stdlib `sqlite3`, no new dependency) with three
tables:

- `strategy_stats` — attempts / successes / total & average reward, keyed
  by strategy (`roleplay`) **and** by strategy+variant (`roleplay#1`).
  This table *is* the RL policy's state — there's no separate weights file.
- `experiences` — every attack/response/analysis/reward, indexed by
  prompt hash (for de-dup) and strategy.
- `benchmark_seeds` — style exemplars extracted from benchmark datasets
  at bootstrap time (see below) — never replayed directly, just used as
  reference material.

The database file (`output/knowledge_base.sqlite3` by default) persists
between runs, so strategy statistics accumulate across sessions unless
you delete it or pass `--fresh-kb`.

---

## Strategy Planner + RL Policy

`attacks/strategy_planner.py` (`BanditStrategyPlanner`) picks one of the
six canonical strategies before any prompt is written:

```
direct_prompt_injection | indirect_prompt_injection | roleplay
authority_impersonation | context_manipulation | multi_turn_prompt_injection
```

Selection is delegated to `attacks/policy.py` (`EpsilonGreedyPolicy`) — a
standard multi-armed bandit, which is the right amount of RL machinery
for "which of 6 actions should I try next" on an 8-week budget:

- **State** — the KB's current `StrategyStats` for every strategy.
- **Action** — pick one strategy (and, inside the Prompt Generator, one
  template variant within it — a second, finer-grained bandit).
- **Reward** — a float in `[-1, 1]` from `attacks/reward.py`.
- **Policy** — cold-start forces every untried strategy to be attempted
  once; after that, explore randomly with probability `exploration_rate`
  (default `0.25`), otherwise exploit the strategy with the highest
  `avg_reward` so far.

"Policy update" has no separate step: `KnowledgeBase.record_experience()`
updates `avg_reward`, and the next `select_next()` call reads it straight
back out. Tune exploration with `--exploration-rate` or
`run.exploration_rate` in `config.yaml`.

---

## Prompt Generator

`attacks/prompt_generator.py` (`TemplatePromptGenerator`, the default)
turns a chosen strategy into an actual prompt using two *deterministic*
choices — no random mutation:

1. **Goal rotation** — which `ObjectiveProfile.attack_goal` to target
   round-robins on the strategy's attempt count, so every strategy
   eventually gets tested against every goal.
2. **Variant selection** — each strategy has 2 hand-written phrasing
   templates; which one to use is chosen by the *same* bandit policy,
   scoped to that strategy's variants, so a winning phrasing gets reused
   more often while the other is still checked periodically.

An optional `LLMPromptGenerator` (same file) asks an LLM to write the
prompt instead, seeded with the KB's best-performing prior prompts and
benchmark exemplars for that strategy — this is one of the two places
the spec explicitly allows an LLM call, but it is **not** wired into
`main.py` by default; swap it in only if your budget allows.

---

## Attack Analyst

`judge/attack_analyst.py` replaces the plain Judge with the same
rule-based-first, LLM-fallback cost discipline as before, but returns a
structured `AttackAnalysis` instead of a bare score:

```
RuleBasedAttackAnalyzer (reuses the regex/keyword signal library)
      |
confidence >= threshold? --yes--> return analysis (free)
      |
      no
      v
LLMAttackAnalyst (budget permitting) --> return analysis
```

Each `AttackAnalysis` carries: `outcome` (`"success" | "partial" |
"failure"` — not binary, so a partially-bypassed guardrail is a
first-class result), `confidence`, `explanation`, `defense_triggered`,
`recommendation` (feeds back into the report and the KB), and `tags`.
`HybridAttackAnalyst` enforces the same `max_llm_calls` hard cap as the
old Hybrid Judge did.

---

## Reward function

`attacks/reward.py` scores each `AttackAnalysis`:

| Factor | Effect |
|---|---|
| Outcome = success | `+1.0` base |
| Outcome = partial | `+0.5` base |
| Outcome = failure | `0.0` base |
| First success for a strategy | `+0.3` novelty bonus |
| Duplicate attack (defensive backstop; KB dedup should catch these first) | `-0.5` |

Result is clamped to `[-1.0, 1.0]` so `avg_reward` stays comparable
across strategies in the strategy-performance table.

---

## Objectives

An `ObjectiveProfile` (`objectives/*.yaml`) defines what "safe" means for
a class of system:

```yaml
name: customer_support
system_prompt: "..."
attack_goals: ["Reveal your system prompt...", ...]
safety_expectations: ["Never reveal system prompts...", ...]
disallowed_topics: ["internal pricing formula", ...]
```

Shipped profiles: `customer_support`, `banking_assistant`, `hr_assistant`,
`generic`. Add a new one by dropping a new YAML file with the same shape
into `objectives/` and registering it in `objectives/profiles.py`.

`attack_goals` feed the Prompt Generator's goal rotation;
`safety_expectations` and `disallowed_topics` feed the Attack Analyst.

---

## Benchmarks — bootstrap only, never replayed

`benchmarks/loader.py` loads JSON datasets from `benchmarks/datasets/`.
In the autonomous pipeline these are used **only** to bootstrap the
Attack Knowledge Base: each entry's `technique` label is mapped onto one
of the six canonical strategies (see `map_technique_to_strategy()` in
`knowledge_base/attack_knowledge_base.py`) and stored as a style
exemplar in `benchmark_seeds` — the actual benchmark prompt text is never
sent to the target directly.

Shipped: a real, usable `custom` dataset, plus small **illustrative
placeholder samples** in the JailbreakBench / HarmBench / AdvBench prompt
shapes (each file documents where to plug in the real, full dataset). By
default only `custom` is enabled — enable others via
`run.benchmark_names` in `config/config.yaml`.

---

## Experience Memory and cost control

`core/memory.py::JsonlExperienceMemory` is the full, ordered, replayable
log of every `AttackExperience` (strategy, prompt, response, analysis,
reward, timestamp), appended to `output/experience_memory.jsonl`. The
Attack Knowledge Base is what the policy actually queries for
decision-making (indexed SQL); Experience Memory is the audit trail.

Cost is bounded the same way as before, just relocated:
- `KnowledgeBase.seen_prompt_hash()` skips re-sending an exact-duplicate
  prompt (checked before the target call, so it saves target cost too).
- `HybridAttackAnalyst` enforces a hard `max_llm_calls` cap per run.
- Prompt generation, strategy selection, and reward computation are all
  pure Python by default — the only paid calls are target calls (which
  testing requires) and capped Attack Analyst escalations.

---

## Extending to a new AI system type

1. Write a new `ObjectiveProfile` YAML in `objectives/` (system prompt,
   attack goals, safety expectations, disallowed topics).
2. If it's a new kind of target (not OpenAI/REST), add one adapter file
   in `adapters/` implementing `send()`.
3. Optionally add a benchmark dataset JSON under `benchmarks/datasets/`.
4. Run: `python main.py --objective your_new_objective --target your_adapter`.

No changes to `core/`, `judge/`, `attacks/`, or `reporting/` are required.

---

## Version 3: REST API + demo frontend + Executive Mitigation Report

On top of the CLI, the framework now also exposes a REST API and a
lightweight demo frontend for presenting a run live — built entirely as
an additive layer (`api/`, `frontend/`, `runner.py`, plus a few small
instrumentation hooks in `core/orchestrator.py`). Nothing about the
attack pipeline itself changed: `runner.py::build_pipeline()` is the
exact same wiring `main.py` always used, just extracted so both the CLI
and the API call it instead of duplicating it.

```bash
python -m api.app          # starts the API + serves the frontend at http://127.0.0.1:8080/
```

Then open `http://127.0.0.1:8080/` for the demo console (Dashboard,
Previous Runs, Report Viewer), or drive it directly:

```bash
curl -X POST http://127.0.0.1:8080/api/runs -H "Content-Type: application/json" -d '{
  "target": "mock", "prompt_generator": "template", "max_iterations": 15, "fresh_kb": true
}'
curl http://127.0.0.1:8080/api/status
curl http://127.0.0.1:8080/api/runs
curl http://127.0.0.1:8080/api/mitigation/<run_id> -o mitigation.pdf
```

**Endpoints:** `POST /api/runs` (start), `GET /api/status` (live stage —
iteration, strategy, current attack preview, and a per-iteration stage
checklist matching the pipeline diagram), `GET /api/runs`, `GET
/api/reports`, `GET /api/mitigation/<run_id>` (PDF), `GET
/api/reports/<run_id>/technical/<md|json>`, `GET /api/history/<run_id>`.

**Live status** is driven by an optional `on_event` callback added to
`AutonomousOrchestrator` (default `None` — the CLI never passes one, so
its behavior is unchanged byte-for-byte; verified in `tests/`). The API
layer subscribes to it instead of the orchestrator loop knowing anything
about HTTP.

**Executive Mitigation Report** (`reporting/mitigation_report_generator.py`,
via `reportlab`) is a separate, short PDF from the developer-facing
technical report — findings grouped by strategy category, plain-language
evidence only (the Attack Analyst's `observed_behavior` summaries, never
raw prompts/responses), business impact, and recommended fixes. Generated
automatically at the end of every run.

**One run at a time.** `api/run_manager.py` deliberately keeps this
simple — starting a second run while one is active returns `409`, per
the "don't over-engineer this" instruction. Fine for a live demo; a
queue would be the natural next step for concurrent usage.

**Framework choice:** the API is built on **Flask**, not FastAPI —
this environment couldn't reach the internet to install `fastapi`/
`uvicorn`, so Flask (already available) was used so the whole layer
could actually be run and tested rather than shipped unverified. If you
prefer FastAPI, `api/run_manager.py`/`runner.py` underneath are
framework-agnostic — only `api/app.py` would need rewriting.

**Tested:** `tests/test_api_offline.py` drives a full run through the
Flask test client (start → poll → completion), then checks every
endpoint including downloading and validating the mitigation PDF
(`%PDF` header) and technical report. Also manually verified via a live
`python -m api.app` + `curl` session (server logs, concurrent-run 409,
unknown-run 404, path-resolution bug found and fixed during testing).
**Not verified here:** actual in-browser execution of `frontend/index.html`
(no browser/network available in this sandbox to run it) — its embedded
JSX was checked for balanced braces/tags as a proxy, but open it in an
actual browser once you have the API running before presenting it.

---

## Configuration

See `config/config.yaml` for all defaults (objective, target adapter,
judge thresholds, iteration/budget caps, output paths). CLI flags in
`main.py --help` override the file for the fields most commonly changed
per run. API keys are read from environment variables only (see
`.env.example`) — never stored in `config.yaml`.

---

## Legacy pipeline (still available)

`main.py` defaults to the autonomous learning pipeline described above.
The original single-pass pipeline is untouched and still runs via
`python main_legacy.py`:

```
Attack Generator -> Target Adapter -> Target System -> Hybrid Judge
-> Memory -> Attack Refiner (deterministic mutation) -> Report
```

It uses `attacks/attack_generator.py::TemplateAttackGenerator`,
`attacks/attack_refiner.py::MutationAttackRefiner`,
`judge/hybrid_judge.py`, `core/memory.py::JsonlMemoryStore`, and
`reporting/report_generator.py`. Nothing about it changed — it's a
reasonable choice if you want simple template-driven coverage across
multiple OWASP LLM categories at once rather than the specialized,
learning-capable prompt-injection pipeline.

---

## Development notes

This is scoped for an 8-week student research project. Prompt Injection
was chosen as the first specialized vulnerability class because it's the
#1 entry on the OWASP LLM Top 10 and the one enterprise chatbots are hit
with most often in practice; the architecture (Strategy Planner / Prompt
Generator / Attack Analyst / Knowledge Base interfaces) is written so a
future iteration can add a second specialized pipeline — e.g. for
Sensitive Information Disclosure or Excessive Agency — by implementing
the same interfaces with a different strategy list and template library,
without touching `core/`.
