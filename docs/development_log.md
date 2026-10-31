# Agentic CRM — Development Log

> **AI WORKFLOW RULE:**
>
> Before modifying the project, read this file first.
>
> Then read `docs/architecture.md` and `docs/roadmap.md` only if needed.
>
> Do NOT reread the entire repository unless the current task genuinely requires it.
>
> Use this development log as the compact memory of previous work.
>
> Continue from the current state instead of rebuilding or re-understanding completed milestones.

---

## Current State

```
PROJECT: Agentic CRM
Stack:   Python 3.13 · SQLite (aiosqlite) · pytest · asyncio · LangGraph
Repo:    GitHub (main branch) · Conventional Commits

PROGRESS
│
├── Phase 1 — Foundation
│   ├── 1.1 Scaffold & Config         ✅  (pyproject.toml, config.py, .env.example, .gitignore)
│   ├── 1.2 Database & Migrations     ✅  (aiosqlite, connection manager, migration runner, schemas)
│   └── 1.3 Task Model & Queue        ✅  (Task dataclass, SQLite-backed queue, status transitions, priority)
│
├── Phase 2 — Provider Infrastructure
│   └── 2.1 Provider Interface & Mgr  ✅  (BaseProvider ABC, ProviderManager, health/circuit breaker, committed 79b3866)
│
├── Phase 3 — LangGraph Foundation    (COMPLETE ✅)
│   ├── 3.1 Core & State Patterns     ✅  (TypedDict state, deterministic nodes, sequential graph, compile/invoke)
│   ├── 3.2 Execution Topologies      ✅  (Conditional branching, iterative loops, parallel fan-out/in)
│   └── 3.3 Provider/Task Integration ✅  (Task-to-Graph mapping, ProviderManager, MockProvider, TaskExecutor)
│
├── Phase 4 — Agent Hierarchy         (COMPLETE ✅)
│   ├── 4.1 Grandparent Orchestrator  ✅  (Top-level domain router, StateGraph, handler nodes)
│   ├── 4.2 Sales Domain Agent        ✅  (Sales subdomain classifier, StateGraph, subdomain handlers)
│   └── 4.3 CLI Intake Layer          ✅  (argparse, DB task lifecycle, orchestrator execution)
│
├── Phase 5 — Concrete Providers & Routing (IN PROGRESS ⏳)
│   ├── 5.1 OpenRouter Provider       ✅  (BaseProvider, OpenRouter API completions, free models, health checks)
│   ├── 5.2 LLM-Assisted Orchestrator ✅  (Deterministic + OpenRouter LLM classification fallback)
│   ├── 5.3 Concrete Providers        ⏳  (DEFERRED: Ollama local provider / Groq)
│   └── 5.4 Task / Model Router       ⏳  (DEFERRED: Capability-based routing & fallback chain)
│
├── Phase 6 — Reliability & Recovery  ⏳  (Worker, Idempotency, Audit)
├── Phase 7 — First CRM Feature       ⏳  (Leads CRUD, Scoring, Integration)
└── Phase 8 — API & Scheduling        ⏳  (FastAPI, APScheduler)
```

**Last verified test count:** 392 tests passed (exit code 0)

---

## Completed

| Step | Summary | Key Files | Tests |
|------|---------|-----------|-------|
| 1.1 Scaffold & Config | Project structure, config from env vars | `src/config.py`, `pyproject.toml`, `.env.example` | `tests/test_config.py` |
| 1.2 Database | aiosqlite connection, migration runner, initial schemas | `src/database/connection.py`, `src/database/migrations/` | `tests/test_database.py` |
| 1.3 Task & Queue | Task model, persistent queue, status lifecycle, priority | `src/core/task.py`, `src/core/queue.py` | `tests/test_task.py`, `tests/test_queue.py` |
| 2.1 Provider System | BaseProvider ABC, ProviderManager registry, health checks, circuit breaker, rate-limit backoff, paid-provider rejection | `src/providers/base.py`, `src/providers/manager.py`, `src/providers/health.py`, `src/providers/exceptions.py` | `tests/test_provider_base.py`, `tests/test_provider_manager.py` |
| 3.1 LangGraph Core | LangGraph dependency, typed BasicState, deterministic nodes, sequential graph flow: START -> node_one -> node_two -> END | `src/graph/state.py`, `src/graph/basic_graph.py`, `src/graph/__init__.py` | `tests/test_langgraph_basic.py` (5 tests) |
| 3.2 Execution Topologies | Conditional branching (`add_conditional_edges`), iterative loops with max safety ceiling, parallel branches with `operator.add` fan-in | `src/graph/conditional_graph.py`, `src/graph/loop_graph.py`, `src/graph/parallel_graph.py` | `tests/test_langgraph_topologies.py` (7 tests) |
| 3.3 Provider & Task Integration | Task-to-Graph mapping, ProviderManager async invocation, MockProvider, TaskExecutor lifecycle (PENDING -> RUNNING -> COMPLETED/FAILED) | `src/providers/mock_provider.py`, `src/graph/task_state.py`, `src/graph/task_graph.py`, `src/core/task_executor.py` | `tests/test_task_graph.py`, `tests/test_task_executor.py` (9 tests) |
| 4.1 Grandparent Orchestrator | Hierarchical top-level dispatcher: OrchestratorState schema, deterministic rule-based domain classifier, decoupled domain handler nodes (sales, marketing, customer_service, data, unknown), compiled LangGraph StateGraph, sync/async GrandparentOrchestrator | `src/agents/orchestrator/state.py`, `src/agents/orchestrator/classifier.py`, `src/agents/orchestrator/handlers.py`, `src/agents/orchestrator/orchestrator.py`, `src/agents/__init__.py` | `tests/test_orchestrator.py` (37 tests) |
| 4.2 Sales Domain Agent Foundation | SalesAgentState schema, deterministic sales subdomain classifier (`lead_management`, `opportunity_management`, `deal_management`, `general_sales`), decoupled subdomain handlers, compiled LangGraph StateGraph, sync/async SalesDomainAgent, Grandparent Orchestrator integration | `src/agents/sales/state.py`, `src/agents/sales/classifier.py`, `src/agents/sales/handlers.py`, `src/agents/sales/agent.py`, `src/agents/sales/__init__.py`, `src/agents/__init__.py` | `tests/test_sales_agent.py` (39 tests) |
| 4.3 CLI Intake Layer | Command-line task intake: ArgumentParser (`argparse`), `submit_task` persistent task queue intake + DB lifecycle update (`PENDING -> RUNNING -> COMPLETED/FAILED`), Grandparent Orchestrator execution, `format_task_output` (text/json), `src/main.py` entrypoint | `src/cli/parser.py`, `src/cli/intake.py`, `src/cli/__init__.py`, `src/main.py` | `tests/test_cli.py` (13 tests) |
| 5.1 OpenRouter Provider | First external AI provider conforming to `BaseProvider` & `ProviderManager`. Integrates OpenRouter OpenAI-compatible completions API, reads credentials securely from env/settings, configurable default model (`nvidia/nemotron-3.5-lightning:free`), health & availability checks, token/latency tracking, robust error mapping, and secret sanitization | `src/providers/openrouter.py`, `src/providers/__init__.py`, `src/config.py`, `.env.example`, `pyproject.toml` | `tests/test_openrouter_provider.py` (18 tests) |
| 5.2 LLM-Assisted Orchestrator Classification | Added controlled LLM-assisted domain classification fallback to Grandparent Orchestrator. Deterministic classifier remains primary. If uncertain, queries OpenRouter via ProviderManager using configured model (`nvidia/nemotron-3.5-lightning:free`). Validates strictly to supported domains with safe fallback to 'unknown' on error or invalid output. | `src/agents/orchestrator/classifier.py`, `src/agents/orchestrator/orchestrator.py`, `src/agents/orchestrator/state.py`, `src/agents/orchestrator/__init__.py` | `tests/test_orchestrator_llm.py` (40 tests) |

---

## Current

**Active milestone:** Milestone 5.2 complete. Preparing for Milestone 5.3 — Local Provider (Ollama) / Additional Providers (Groq).

**Milestone 5.2 Status:** COMPLETE
- Integrated **LLM-Assisted Domain Classification** into `GrandparentOrchestrator` as an optional fallback when deterministic classification is uncertain.
- Preserved **Deterministic Classification** as primary: tasks with strong keyword signals or explicit overrides route immediately without calling the LLM.
- Extended `OrchestratorState` with `classification_method` (`"deterministic"`, `"llm"`, `"fallback"`).
- Wired through **ProviderManager** abstraction (`provider_manager.get_available_provider()`), keeping orchestrator completely decoupled from OpenRouter HTTP/API details.
- Validated LLM responses strictly against `SUPPORTED_DOMAINS` (`sales`, `marketing`, `customer_service`, `data`, `unknown`), rejecting arbitrary output.
- Robust failure handling: falls back gracefully to `unknown` upon provider errors, timeouts, empty responses, or malformed outputs.
- Tested: 40 focused unit tests passing; 392 total regression tests passing (exit code 0).
- Live API verification performed: 1 real test on OpenRouter with `nvidia/nemotron-3.5-lightning:free` correctly classified an ambiguous task as `sales` and routed to the Sales Domain Agent.

---

## Known Issues

None currently.

---

## Important Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Python version | 3.13 (runtime), 3.11+ compatible | Broad compatibility |
| Database | SQLite via aiosqlite | Zero-install, file-based, dev-appropriate |
| ORM | SQLAlchemy Core (no ORM) | Type safety without overhead |
| Async | Full asyncio | Needed for concurrent provider calls |
| LangGraph | Core state-machine layer | Graph-based orchestration for orchestrator & domain agents |
| Graph State | TypedDict (`total=False`) | Canonical LangGraph pattern for partial state updates |
| DB / Graph Isolation | TaskExecutor coordinator | Keeps graph nodes pure; database operations stay outside graphs |
| Parallel State Reducer | `Annotated[List, operator.add]` | Prevents state update conflicts during parallel fan-in |
| Loop Safety | Explicit max iterations ceiling | Prevents graph infinite execution loops under any condition |
| First External Provider | OpenRouter | Multi-model catalog, OpenAI-compatible API, free models |
| First Free Model | `nvidia/nemotron-3.5-lightning:free` | Available on OpenRouter free tier |
| Secret Sanitization | Redact API key in all errors & exceptions | Eliminates risk of secret leakage in logs/traces |
| First LLM Integration | Grandparent Orchestrator fallback | Deterministic first; LLM only assists when uncertain |
| Provider Decoupling | Use ProviderManager abstraction | Orchestrator never directly couples to OpenRouter endpoint |
| First CRM domain | Leads | Most self-contained workflow |
| License | MIT | Simple, permissive |
| Cost policy | $0 ceiling | Never auto-escalate to paid APIs |

---

## Next Step

**Milestone 5.3 — Local Provider (Ollama) / Additional Providers (Groq)**

Implement additional concrete providers implementing `BaseProvider`:
- `OllamaProvider`: local SLM execution via Ollama HTTP API.
- `GroqProvider`: cloud execution with fast inference.
- Register into `ProviderManager` with health checks and rate limit handling.
- Reference: `docs/roadmap.md` → Phase 5, Milestone 5.3

---

---

## Git State

```
Branch:      main
Remote:      origin/main
Last commit: 84d9a56  feat: implement OpenRouter provider (Milestone 5.1)

Uncommitted work:
  MODIFIED  docs/roadmap.md
  MODIFIED  docs/development_log.md
```

---

## Testing Policy

- During implementation: focused tests only.
- After meaningful milestone: run relevant verification.
- Before declaring complete: run final test suite.
- Do NOT rerun identical tests when no code changed.
- Do NOT spend excessive effort on non-blocking issues.

---

## Error Log

_No active issues._

Template for future entries:
```
⚠️ ISSUE
Location: <file/module>
Problem: <one-line description>
Status: OPEN / FIXED
Resolution: <one-line description>
```

---

## History

| Date | Event |
|------|-------|
| 2026-10-22 | Architecture document and roadmap created |
| 2026-10-22 | Steps 2A–2C implemented (scaffold, database, task queue) — committed as `e7568c0` |
| 2026-10-22 | Milestone 2C report — committed as `899c8aa` |
| 2026-10-31 | Step 2.1 Provider System implemented. Committed and pushed as `79b3866`. |
| 2026-10-31 | Strategic Roadmap Realignment: Prioritized Phase 3 LangGraph Foundation. Committed and pushed as `4b6bc29`. |
| 2026-10-31 | Milestone 3.1: LangGraph Core & State Patterns implemented. 229 tests passed (exit code 0). Committed and pushed as `2520cfb`. |
| 2026-10-31 | Milestone 3.2: Execution Topologies (Conditional, Loop, Parallel) implemented. 236 tests passed (exit code 0). Committed and pushed as `2839712`. |
| 2026-10-31 | Milestone 3.3: Provider & Task Integration implemented. 245 tests passed (exit code 0). Committed and pushed as `527d011`. |
| 2026-10-31 | Milestone 4.1: Grandparent Orchestrator implemented. 282 tests passed (exit code 0). Committed and pushed as `6f2672d`. |
| 2026-10-31 | Milestone 4.2: Sales Domain Agent Foundation implemented. 321 tests passed (exit code 0). Committed and pushed as `3589b25`. |
| 2026-10-31 | Milestone 4.3: CLI Intake Layer implemented. 334 tests passed (exit code 0). Committed and pushed as `5ad7461`. |
| 2026-10-31 | Milestone 5.1: OpenRouter Provider implemented. 352 tests passed (exit code 0). Committed and pushed as `84d9a56`. |
| 2026-10-31 | Strategic Roadmap Realignment (Option A): Milestone 5.2 set to LLM-Assisted Orchestrator Classification (OpenRouter); Ollama/Groq deferred to Milestone 5.3. Committed and pushed as `c5ab420`. |
| 2026-10-31 | Milestone 5.2: LLM-Assisted Orchestrator Classification implemented. 392 tests passed (exit code 0). |
