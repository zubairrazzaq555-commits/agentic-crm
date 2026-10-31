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
├── Phase 5 — Concrete Providers, CRM Foundation & Routing (IN PROGRESS ⏳)
│   ├── 5.1 OpenRouter Provider       ✅  (BaseProvider, OpenRouter API completions, free models, health checks)
│   ├── 5.2 LLM-Assisted Orchestrator ✅  (Deterministic + OpenRouter LLM classification fallback)
│   ├── 5.3 Hierarchy Design          ✅  (4 levels, 20 specialist agents, tools vs agents, 8GB/16GB RAM strategy)
│   ├── 5.4 CRM Core DB & Sales Data  ✅  (Leads, Accounts, Contacts, Opps, Deals schemas, repos, services, tools)
│   ├── 5.5 Sales Agent Execution     ✅  (Real CRM operations, intent extraction, graph integration, CLI execution)
│   ├── 5.6 Local Provider (Ollama)   ⏳  (NEXT: Ollama local SLM execution / Groq)
│   └── 5.7 Task / Model Router       ⏳  (DEFERRED: Capability-based routing & fallback chain)
│
├── Phase 6 — Reliability & Recovery  ⏳  (Worker, Idempotency, Audit)
├── Phase 7 — First CRM Feature       ⏳  (Leads CRUD, Scoring, Integration)
└── Phase 8 — API & Scheduling        ⏳  (FastAPI, APScheduler)
```

**Last verified test count:** 425 tests passed (exit code 0)

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
| 5.3 Complete CRM Agent Hierarchy Design | Designed 4-level enterprise CRM Agent Hierarchy (`docs/CRM_AGENT_HIERARCHY.md`): Level 1 Orchestrator, Level 2 Domain Agents (Sales, Marketing, Service, Data), Level 3 Specialist Child Agents (20 total, 5 per domain), Level 4 Sub-specialists vs Deterministic Tools. Established strict rule: CRUD/SQL/calculations must never invoke models. Defined 8GB (≤1.5B model, ≤2.2GB RAM) and 16GB (≤3.8B model, ≤5.5GB RAM) memory budgets and SLM-first local execution roadmap. | `docs/CRM_AGENT_HIERARCHY.md`, `docs/architecture.md`, `docs/roadmap.md`, `docs/AGENT_HIERARCHY_AUDIT.md` | Zero regression (392 tests passing) |
| 5.4 CRM Core Database & Sales Data Foundation | Foundational CRM database architecture for Sales domain: Leads, Accounts, Contacts, Opportunities, and Deals. Enabled foreign key enforcement in SQLite (`PRAGMA foreign_keys = ON;`), relational cascades, unique constraints, and schema registration via `metadata.create_all()`. Created clean Repositories (`LeadRepository`, `AccountRepository`, `ContactRepository`, `OpportunityRepository`, `DealRepository`), Services (`LeadService`, `AccountService`, `ContactService`, `OpportunityService`, `DealService`), and deterministic Level 4 Python tools (`create_lead_tool`, `qualify_lead_tool`, `convert_lead_tool`, `create_account_tool`, `create_deal_tool`, etc.). Bound services to `SalesDomainAgent`. | `src/crm/models.py`, `src/crm/repositories/`, `src/crm/services/`, `src/crm/tools/`, `src/crm/__init__.py`, `src/database/connection.py`, `src/agents/sales/` | `tests/test_crm_database.py`, `tests/test_crm_repositories.py`, `tests/test_crm_services.py`, `tests/test_crm_tools.py` (33 new tests, 425 total passing) |

---

## Current

**Active milestone:** Milestone 5.5 complete. Preparing for Milestone 5.6 — Local Provider (Ollama / Local SLM).

**Milestone 5.5 Status:** COMPLETE
- Implemented deterministic intent parser (`extract_sales_intent`) in `src/agents/sales/intent.py` supporting all 5 Sales subdomains:
  - Lead Management (`create_lead`, `search_leads`, `qualify_lead`, `convert_lead`)
  - Contact Management (`create_contact`, `search_contacts`)
  - Account Management (`create_account`, `search_accounts`, `account_summary`)
  - Opportunity Management (`create_opportunity`, `search_opportunities`, `advance_stage`)
  - Deal Management (`create_deal`, `search_deals`, `close_deal`)
- Expanded `SalesDomainAgent` LangGraph topology to include dedicated nodes and conditional edges for `contact_handler` and `account_handler`.
- Connected all Sales subdomain handlers to real CRM services and deterministic Level 4 Python tools against SQLite.
- Preserved Grandparent Orchestrator delegation contract (`execution_status = "SUCCESS"` upon delegation completion, with actual CRM result stored in `delegation_result["sales_agent_result"]`).
- Maintained backward compatibility for legacy abstract tasks and CLI tests without regressions.
- Ensured event loop safety for SQLAlchemy `AsyncEngine` across async/sync thread boundaries.
- Updated CLI intake layer (`submit_task`, `format_task_output`) with JSON serialization of datetimes and human-readable CRM execution reporting.
- Added comprehensive test suite in `tests/test_sales_execution.py` (16 tests).
- All 441 tests passing (100% pass rate, exit code 0).

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
| SQLite Foreign Keys | Enabled via PRAGMA foreign_keys = ON connection event listener | Enforces referential integrity and ON DELETE CASCADE / SET NULL |
| CRM Architecture | 3-tier: Repositories -> Services -> Tools | Clean separation of persistence, business rules, and agent-callable functions |
| Async | Full asyncio | Needed for concurrent provider calls and async DB operations |
| LangGraph | Core state-machine layer | Graph-based orchestration for orchestrator & domain agents |
| Graph State | TypedDict (`total=False`) | Canonical LangGraph pattern for partial state updates |
| DB / Graph Isolation | TaskExecutor coordinator & Level 4 Tools | Keeps graph nodes pure; database operations stay outside graphs |
| Parallel State Reducer | `Annotated[List, operator.add]` | Prevents state update conflicts during parallel fan-in |
| Loop Safety | Explicit max iterations ceiling | Prevents graph infinite execution loops under any condition |
| First External Provider | OpenRouter | Multi-model catalog, OpenAI-compatible API, free models |
| First Free Model | `nvidia/nemotron-3.5-lightning:free` | Available on OpenRouter free tier |
| Secret Sanitization | Redact API key in all errors & exceptions | Eliminates risk of secret leakage in logs/traces |
| First LLM Integration | Grandparent Orchestrator fallback | Deterministic first; LLM only assists when uncertain |
| Provider Decoupling | Use ProviderManager abstraction | Orchestrator never directly couples to OpenRouter endpoint |
| First CRM domain | Leads & Sales | Most self-contained workflow |
| License | MIT | Simple, permissive |
| Cost policy | $0 ceiling | Never auto-escalate to paid APIs |
| Hierarchy Architecture | 4-Level Model (Orchestrator → Domain → Specialist → Tools/Sub-agents) | Separates concerns cleanly; matches enterprise CRM structures (Salesforce) |
| Deterministic Tool Boundary | CRUD/SQL/Calculations strictly Python tools | Never waste model tokens or introduce hallucination risk for simple data operations |
| SLM-First Local Strategy | Small models (≤1.5B on 8GB RAM, ≤3.8B on 16GB RAM) | Enables complete offline operation on commodity laptops without cloud lock-in |
| Memory Management | Lazy model loading & single-model concurrency | Keeps memory within strict 2.2GB (8GB RAM) and 5.5GB (16GB RAM) budgets |
| Subdomain Handler Status Contract | `status: "COMPLETED" if success else "FAILED"`, `success: bool`, `error: Optional[str]` | Aligns with LangGraph node completion while distinguishing business logic outcome |
| Orchestrator Delegation Contract | `execution_status: "SUCCESS"` on completed delegation, nested `sales_agent_result` for domain outcome | Decouples pipeline delegation health from domain-level CRM operation results |

---

## Next Step

**Milestone 5.6 — Local Provider (Ollama / Local SLMs)**

Implement `OllamaProvider` conforming to `BaseProvider`:
- Local SLM execution via Ollama HTTP API.
- Support for target lightweight models (Qwen2.5-1.5B, Phi-3-mini 3.8B).
- Register into `ProviderManager` with health check, availability detection, and zero-cloud fallback.
- Reference: `docs/roadmap.md` → Phase 5, Milestone 5.6

---

## Git State

```
Branch:      main
Remote:      origin/main
Last commit: 3d31dda  feat: implement LLM-assisted orchestrator classification (Milestone 5.2)

Uncommitted work:
  CREATED   docs/CRM_AGENT_HIERARCHY.md
  CREATED   docs/AGENT_HIERARCHY_AUDIT.md
  MODIFIED  docs/architecture.md
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
| 2026-10-31 | Milestone 5.2: LLM-Assisted Orchestrator Classification implemented. 392 tests passed (exit code 0). Committed and pushed as `3d31dda`. |
| 2026-10-31 | Milestone 5.3: Complete CRM Agent Hierarchy Design implemented (`docs/CRM_AGENT_HIERARCHY.md`). 392 tests passed (exit code 0). Committed and pushed as `4196f50`. |
| 2026-10-31 | Milestone 5.4: CRM Core Database & Sales Data Foundation implemented (Leads, Accounts, Contacts, Opps, Deals schemas, repos, services, tools). 425 tests passed (exit code 0). |
| 2026-10-31 | Milestone 5.5: Sales Agent Execution & CRM Integration implemented (real CRM operations, intent extraction, LangGraph integration, CLI execution). 441 tests passed (exit code 0). |
