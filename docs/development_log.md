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
Stack:   Python 3.13 · SQLite (aiosqlite) · pytest · asyncio
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
├── Phase 3 — LangGraph Foundation    ⏳  (NEXT: State -> Node -> Graph -> Edge -> Compile -> Invoke)
│
├── Phase 4 — Agent Hierarchy         ⏳  (Orchestrator, Sales Agent, CLI Intake)
│
├── Phase 5 — Concrete Providers      ⏳  (DEFERRED: Ollama, Cloud Gemini/Groq, Model Router)
│
├── Phase 6 — Reliability & Recovery  ⏳  (Worker, Idempotency, Audit)
├── Phase 7 — First CRM Feature       ⏳  (Leads CRUD, Scoring, Integration)
└── Phase 8 — API & Scheduling        ⏳  (FastAPI, APScheduler)
```

**Last verified test count:** 224 tests passed (exit code 0)

---

## Completed

| Step | Summary | Key Files | Tests |
|------|---------|-----------|-------|
| 1.1 Scaffold & Config | Project structure, config from env vars | `src/config.py`, `pyproject.toml`, `.env.example` | `tests/test_config.py` |
| 1.2 Database | aiosqlite connection, migration runner, initial schemas | `src/database/connection.py`, `src/database/migrations/` | `tests/test_database.py` |
| 1.3 Task & Queue | Task model, persistent queue, status lifecycle, priority | `src/core/task.py`, `src/core/queue.py` | `tests/test_task.py`, `tests/test_queue.py` |
| 2.1 Provider System | BaseProvider ABC, ProviderManager registry, health checks, circuit breaker, rate-limit backoff, paid-provider rejection | `src/providers/base.py`, `src/providers/manager.py`, `src/providers/health.py`, `src/providers/exceptions.py` | `tests/test_provider_base.py`, `tests/test_provider_manager.py` |

---

## Current

**Active status:** Strategic realignment complete. Ready to implement Phase 3 (LangGraph Foundation).

**Last completed:** Step 2.1 (Provider Interface & Manager) — committed and pushed (`79b3866`).

---

## Strategic Realignment

- **Previous planned next step:**
  → Milestone 2.2: Ollama Local Provider
- **Decision:**
  → Deferred to Phase 5 (along with Cloud Providers and Model Router).
- **Reason:**
  → LangGraph foundation can be developed and validated using deterministic/fake providers without requiring live model integrations.
- **New next milestone:**
  → Phase 3: LangGraph Foundation (Milestone 3.1 — LangGraph Core & State Patterns)
- **Remaining dependencies:**
  → Add `langgraph` dependency; existing `ProviderManager` and `Task` model provide all needed substrate.

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
| Concrete Providers | Deferred to Phase 5 | Fake/mock providers via ProviderManager suffice for LangGraph |
| First CRM domain | Leads | Most self-contained workflow |
| License | MIT | Simple, permissive |
| Cost policy | $0 ceiling | Never auto-escalate to paid APIs |

---

## Next Step

**Milestone 3.1 — LangGraph Core & State Patterns**

Implement foundational LangGraph patterns in `src/graph/`:
- Add `langgraph` to dependencies
- Define TypedDict / Pydantic State schemas
- Build core graph pattern: `State -> Node -> Graph -> Edge -> Compile -> Invoke`
- Unit tests validating state flow and node execution

Reference: `docs/roadmap.md` → Phase 3, Milestone 3.1

---

## Git State

```
Branch:      main
Remote:      origin/main
Last commit: 79b3866  feat: implement Step 2D provider interface and manager, add development log

Uncommitted changes:
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
| 2026-10-31 | Strategic Roadmap Realignment: Prioritized Phase 3 LangGraph Foundation; deferred Ollama, Cloud Providers, and Model Router to Phase 5. |
