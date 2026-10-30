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
├── Phase 3 — LangGraph Foundation    (ACTIVE)
│   ├── 3.1 Core & State Patterns     ✅  (TypedDict state, deterministic nodes, sequential graph, compile/invoke)
│   ├── 3.2 Execution Topologies      ⏳  (NEXT: Conditional routing, iterative loops, parallel fan-out/in)
│   └── 3.3 Provider/Task Integration ⏳  (Graph wiring with ProviderManager & Task models)
│
├── Phase 4 — Agent Hierarchy         ⏳  (Orchestrator, Sales Agent, CLI Intake)
│
├── Phase 5 — Concrete Providers      ⏳  (DEFERRED: Ollama, Cloud Gemini/Groq, Model Router)
│
├── Phase 6 — Reliability & Recovery  ⏳  (Worker, Idempotency, Audit)
├── Phase 7 — First CRM Feature       ⏳  (Leads CRUD, Scoring, Integration)
└── Phase 8 — API & Scheduling        ⏳  (FastAPI, APScheduler)
```

**Last verified test count:** 229 tests passed (exit code 0)

---

## Completed

| Step | Summary | Key Files | Tests |
|------|---------|-----------|-------|
| 1.1 Scaffold & Config | Project structure, config from env vars | `src/config.py`, `pyproject.toml`, `.env.example` | `tests/test_config.py` |
| 1.2 Database | aiosqlite connection, migration runner, initial schemas | `src/database/connection.py`, `src/database/migrations/` | `tests/test_database.py` |
| 1.3 Task & Queue | Task model, persistent queue, status lifecycle, priority | `src/core/task.py`, `src/core/queue.py` | `tests/test_task.py`, `tests/test_queue.py` |
| 2.1 Provider System | BaseProvider ABC, ProviderManager registry, health checks, circuit breaker, rate-limit backoff, paid-provider rejection | `src/providers/base.py`, `src/providers/manager.py`, `src/providers/health.py`, `src/providers/exceptions.py` | `tests/test_provider_base.py`, `tests/test_provider_manager.py` |
| 3.1 LangGraph Core | LangGraph dependency, typed BasicState, deterministic nodes, sequential graph flow: START -> node_one -> node_two -> END | `src/graph/state.py`, `src/graph/basic_graph.py`, `src/graph/__init__.py` | `tests/test_langgraph_basic.py` (5 tests) |

---

## Current

**Active milestone:** Milestone 3.1 complete. Preparing for Milestone 3.2.

**Milestone 3.1 Status:** COMPLETE
- Added `langgraph>=0.2.0` dependency to `pyproject.toml`.
- Implemented `BasicState` (TypedDict with input, output, step).
- Created deterministic nodes (`node_one`, `node_two`) operating without external APIs or LLMs.
- Constructed and compiled `StateGraph` with topology `START -> node_one -> node_two -> END`.
- Built convenience invocation helper `run_basic_graph()`.
- Verified 5 focused unit tests + full regression suite (229 passed, exit code 0).

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
| Concrete Providers | Deferred to Phase 5 | Fake/mock providers via ProviderManager suffice for LangGraph |
| First CRM domain | Leads | Most self-contained workflow |
| License | MIT | Simple, permissive |
| Cost policy | $0 ceiling | Never auto-escalate to paid APIs |

---

## Next Step

**Milestone 3.2 — Execution Topologies (Branching, Loops & Parallel)**

Implement and verify non-linear graph patterns in `src/graph/`:
- Conditional routing edges (`add_conditional_edges`)
- Iterative cycles / loops with termination conditions
- Parallel node branches with fan-out and state fan-in / merging
- Focused unit tests verifying routing logic and termination safety

Reference: `docs/roadmap.md` → Phase 3, Milestone 3.2

---

## Git State

```
Branch:      main
Remote:      origin/main
Last commit: 4b6bc29  docs: realign roadmap for LangGraph foundation

Uncommitted work:
  MODIFIED  pyproject.toml
  MODIFIED  docs/development_log.md
  NEW       src/graph/__init__.py
  NEW       src/graph/basic_graph.py
  NEW       src/graph/state.py
  NEW       tests/test_langgraph_basic.py
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
| 2026-10-31 | Milestone 3.1: LangGraph Core & State Patterns implemented. 229 tests passed (exit code 0). |
