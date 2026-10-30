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
├── Phase 2 — Providers & Router
│   ├── 2.1 Provider Interface & Mgr  ✅  (BaseProvider ABC, ProviderManager, health/circuit breaker)
│   ├── 2.2 Ollama Local Provider     ⏳
│   ├── 2.3 Cloud Providers           ⏳
│   └── 2.4 Task/Model Router         ⏳
│
├── Phase 3 — Agent Hierarchy         ⏳  (Orchestrator, Sales Agent, CLI)
├── Phase 4 — Reliability             ⏳  (Worker, Idempotency, Audit)
├── Phase 5 — First CRM Feature       ⏳  (Leads CRUD, Scoring, Integration)
└── Phase 6 — API & Scheduling        ⏳  (FastAPI, APScheduler)
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

**Active milestone:** None — between milestones.

**Last completed:** Step 2.1 (Provider Interface & Manager) — implemented and tested but **not yet committed to Git**.

**Immediate action needed:** Commit Step 2D provider system, then begin Step 2.2 (Ollama Local Provider) or next planned milestone.

---

## Known Issues

None currently.

> Note: `docs/milestone_2c_report.md` is referenced in commit `899c8aa` message but the file does not exist on disk. Non-blocking — the report content is captured in the commit itself. No action required.

---

## Important Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Python version | 3.13 (runtime), 3.11+ compatible | Broad compatibility |
| Database | SQLite via aiosqlite | Zero-install, file-based, dev-appropriate |
| ORM | SQLAlchemy Core (no ORM) | Type safety without overhead |
| Async | Full asyncio | Needed for concurrent provider calls |
| Local LLM | Ollama | Easier model management, HTTP API |
| First CRM domain | Leads | Most self-contained workflow |
| License | MIT | Simple, permissive |
| Cost policy | $0 ceiling | Never auto-escalate to paid APIs |
| LangGraph | Deferred | Custom orchestration first for control |

---

## Next Step

**Milestone 2.2 — Ollama Local Provider**

Implement `OllamaProvider` extending `BaseProvider`:
- Connect to local Ollama HTTP API
- Model selection, timeout handling
- Graceful degradation when Ollama is unavailable
- Mocked tests + optional `--run-live` flag

Reference: `docs/roadmap.md` → Phase 2, Milestone 2.2

---

## Git State

```
Branch:    main
Remote:    origin/main (up to date)
Last commit: 899c8aa  docs: add milestone 2C completion report

Uncommitted work:
  NEW  src/providers/base.py
  NEW  src/providers/exceptions.py
  NEW  src/providers/health.py
  NEW  src/providers/manager.py
  NEW  src/providers/__init__.py
  NEW  tests/test_provider_base.py
  NEW  tests/test_provider_manager.py

Status: Step 2.1 provider code is complete and tested but not yet committed.
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
| 2026-10-31 | Step 2.1 Provider System implemented (BaseProvider, ProviderManager, health, circuit breaker). 224 tests passing. Not yet committed. |
| 2026-10-31 | Development log created (`docs/development_log.md`). |
