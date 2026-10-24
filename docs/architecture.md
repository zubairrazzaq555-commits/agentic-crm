# Agentic CRM — Architecture Document

> **Status:** Draft v0.1 · Planning phase  
> **Last updated:** 2026-10-22  
> **Scope:** Analysis and design — no implementation decisions are final until approved.

---

## 1. System Overview

The Agentic CRM is a modular, hierarchical, event-driven CRM system that combines deterministic logic with intelligent agent orchestration. It is designed to run on a single Windows laptop during development and testing, with zero paid API costs, and to scale toward reliable 24/7 operation as infrastructure becomes available.

### 1.1 Design Principles

| Principle | Implication |
|---|---|
| **Agent frugality** | Use LLM agents only where reasoning, language understanding, or generation is genuinely needed. Prefer Python functions, SQL, rules, conventional ML, or templating everywhere else. |
| **Cost ceiling = $0** | All external APIs must be free-tier. The system must never silently escalate to a paid tier. |
| **Graceful degradation** | When all cloud quotas are exhausted, the system degrades to local models or queues tasks — it never crashes or loses data. |
| **Incremental buildout** | Each milestone is small, testable, and independently useful. |
| **Modularity** | Providers, agents, tools, domain logic, and persistence are behind clean interfaces so any can be swapped or extended without rewriting. |

---

## 2. Technology Stack

### 2.1 Chosen Technologies

| Layer | Technology | Rationale |
|---|---|---|
| **Language** | Python 3.11+ | Rich AI/ML ecosystem, async support, rapid prototyping |
| **Database** | SQLite (via `aiosqlite` + raw SQL or SQLAlchemy Core) | Zero-install, file-based, sufficient for dev/test; can migrate to PostgreSQL later |
| **Task queue** | Custom lightweight queue backed by SQLite | Avoid heavy dependencies (Celery/Redis) on a dev laptop; upgrade path exists |
| **Background workers** | `asyncio` tasks + optional `APScheduler` | No external process manager needed during dev |
| **LLM access (cloud)** | Google Gemini free tier, Groq free tier, OpenRouter free models, HuggingFace Inference API | Multiple free providers with automatic fallback |
| **LLM access (local)** | Ollama (llama.cpp backend) running small models (Phi-3-mini 3.8B, Qwen2-1.5B, Gemma-2B) | Fits in 16 GB RAM on CPU; no GPU required |
| **Web framework** | FastAPI (future phases) | Lightweight, async, OpenAPI docs out of the box |
| **Testing** | pytest + pytest-asyncio | Standard, well-supported |
| **Config/secrets** | python-dotenv + `.env.example` (placeholders only) | No secrets in source; env-var driven |
| **Version control** | Git + GitHub | Branching, PRs, CI readiness |

### 2.2 Alternatives Considered

| Alternative | Why deferred |
|---|---|
| PostgreSQL | Overkill for single-laptop dev; easy migration later via SQLAlchemy |
| Redis + Celery | Heavy infrastructure for dev; SQLite queue is sufficient initially |
| LangChain / LangGraph | Adds large dependency surface; custom orchestration gives more control and learning |
| Django | Heavier than FastAPI; not needed until full web UI phase |
| Vector DB (ChromaDB) | Deferred until RAG/semantic-search features are needed |

---

## 3. Component Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        API / CLI / Event Intake                  │
│                  (FastAPI endpoints, CLI commands, schedulers)    │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                    GRANDPARENT ORCHESTRATOR                       │
│  • Receives tasks from intake layer                              │
│  • Classifies domain (Sales, Service, Marketing, Data, etc.)     │
│  • Delegates to the appropriate Domain Agent                     │
│  • Tracks overall task lifecycle                                 │
│  • May itself be deterministic (rule-based router) initially     │
└───────┬──────────┬──────────┬──────────┬────────────┬────────────┘
        │          │          │          │            │
        ▼          ▼          ▼          ▼            ▼
   ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐
   │ Sales  │ │Service │ │Market- │ │ Data   │ │Integra-  │
   │ Agent  │ │ Agent  │ │ ing    │ │ Agent  │ │tions     │
   │(Parent)│ │(Parent)│ │ Agent  │ │(Parent)│ │Agent     │
   └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └────┬─────┘
       │          │          │          │            │
       ▼          ▼          ▼          ▼            ▼
  ┌─────────────────────────────────────────────────────────┐
  │              SPECIALIST AGENTS & TOOLS                   │
  │  • Lead Scorer (ML model or rules)                       │
  │  • Email Drafter (LLM agent)                             │
  │  • Data Enrichment (API tool)                            │
  │  • Report Generator (template + SQL)                     │
  │  • Calendar Scheduler (deterministic)                    │
  │  • ... (added incrementally)                             │
  └─────────────────────────────────────────────────────────┘
       │          │          │          │            │
       ▼          ▼          ▼          ▼            ▼
  ┌─────────────────────────────────────────────────────────┐
  │               TASK / MODEL ROUTER                        │
  │  Selects execution method per-task:                      │
  │  1. Deterministic code (Python function, SQL, rules)     │
  │  2. Conventional ML/DL model                             │
  │  3. Local SLM (Ollama)                                   │
  │  4. Free cloud LLM (Gemini, Groq, etc.)                 │
  │  5. More capable cloud LLM (only if genuinely needed)    │
  │  ─────────────────────────────────────────               │
  │  • Enforces NO-PAID-FALLBACK policy                      │
  │  • Tracks quotas, rate limits, costs                     │
  │  • Automatic fallback down the capability ladder          │
  └──────────────────────┬──────────────────────────────────┘
                         │
                         ▼
  ┌─────────────────────────────────────────────────────────┐
  │               PROVIDER MANAGER                           │
  │  • Registry of all LLM / API providers                   │
  │  • Health checks, quota tracking, rate-limit backoff     │
  │  • Circuit breaker per provider                          │
  │  • Retry with exponential backoff + jitter               │
  │  • Never escalates to paid tier                          │
  └──────────────────────┬──────────────────────────────────┘
                         │
                         ▼
  ┌─────────────────────────────────────────────────────────┐
  │               PERSISTENCE LAYER                          │
  │  • SQLite database (tasks, CRM entities, config, logs)   │
  │  • Task queue table (pending, in-progress, completed,    │
  │    failed, retry-scheduled)                              │
  │  • Idempotency keys to prevent duplicate side effects    │
  │  • Audit log for all agent decisions                     │
  └─────────────────────────────────────────────────────────┘
```

---

## 4. Component Boundaries & Responsibilities

### 4.1 Intake Layer
- **CLI interface** (Phase 1): Accept tasks as text commands.
- **FastAPI endpoints** (Phase 3+): REST API for external integrations.
- **Scheduler** (Phase 4+): Cron-like triggers for recurring tasks.
- **Responsibility:** Validate input, create a Task record, enqueue it.

### 4.2 Grandparent Orchestrator
- **Initially:** A rule-based Python router (keyword/regex matching to domain).
- **Later:** Can be upgraded to use an LLM for ambiguous task classification.
- **Responsibility:** Receive Task from queue, classify domain, delegate to the correct Domain Agent, track lifecycle (pending → running → success/failure), handle retries at the orchestration level.

### 4.3 Domain Agents (Parents)
- One per CRM domain: Sales, Service, Marketing, Data, Integrations.
- **Built incrementally** — Sales Agent is the first, others added later.
- **Responsibility:** Decompose a domain-level task into sub-tasks, delegate to specialist agents or tools, aggregate results, report back to orchestrator.
- **May or may not use an LLM** — a Sales Agent that only manages leads might be mostly deterministic until it needs to draft personalized emails.

### 4.4 Specialist Agents & Tools
- Focused, single-responsibility units.
- **Agents** (need reasoning): Email Drafter, Meeting Summarizer, etc.
- **Tools** (deterministic): Lead CRUD operations, report SQL queries, data validation, etc.
- **Responsibility:** Execute a specific sub-task, return structured results.

### 4.5 Task / Model Router
- **Separate component** from the agent hierarchy.
- Called by any agent or tool that needs to decide *how* to execute a sub-task.
- Decision logic:
  1. **Can this be done deterministically?** → Use a Python function or SQL query.
  2. **Does this need pattern recognition?** → Use a conventional ML model.
  3. **Does this need language understanding/generation at moderate quality?** → Use a local SLM via Ollama.
  4. **Does this need higher-quality language capabilities?** → Use a free cloud LLM.
  5. **Does this need the most capable model available?** → Use the best available free-tier model. **Never use a paid model.**
- **Routing metadata:** Each task type can declare a `min_capability` level. The router finds the cheapest method that meets it.
- **Quota awareness:** The router queries the Provider Manager for current availability before dispatching.

### 4.6 Provider Manager
- **Registry pattern:** Each provider (Gemini, Groq, Ollama, etc.) is a plugin implementing a common interface.
- **Tracks per-provider:**
  - Remaining quota (requests/day, tokens/minute)
  - Current rate-limit status
  - Health (up/down/degraded)
  - Last error and backoff timer
- **Circuit breaker:** After N consecutive failures, mark provider as "down" for a cooldown period.
- **Strict policy:** A provider's `is_paid` flag is checked before every call. Paid providers are **never** selected automatically.

### 4.7 Persistence Layer
- **SQLite database** with well-defined schemas.
- **Key tables (initial):**
  - `tasks` — id, type, domain, status, payload, result, created_at, updated_at, retry_count, idempotency_key
  - `task_queue` — task_id, priority, scheduled_at, picked_at, worker_id
  - `providers` — name, type, config, quota_remaining, rate_limit_reset_at, is_healthy, is_paid
  - `audit_log` — timestamp, actor (agent/tool), action, task_id, details
  - `leads` (Phase 5+) — first CRM entity
- **Idempotency:** Every task with external side effects carries an idempotency key. Before executing, the system checks if the key was already processed.

---

## 5. Task Lifecycle Flow

```
User/Event → Intake → Create Task record (status: PENDING)
                         │
                         ▼
              Task Queue (SQLite) ← Workers poll / async pick
                         │
                         ▼
              Grandparent Orchestrator
                │  Classify domain
                │  Assign to Domain Agent
                ▼
              Domain Agent
                │  Decompose into sub-tasks
                │  For each sub-task:
                │    ├─ Call Task/Model Router → select execution method
                │    ├─ Execute (deterministic / ML / local SLM / cloud LLM)
                │    ├─ Verify result (schema check, confidence threshold)
                │    ├─ If failed → retry with fallback method
                │    └─ Persist sub-task result
                │  Aggregate results
                ▼
              Orchestrator receives result
                │  Update Task record (status: COMPLETED / FAILED)
                │  Write audit log entry
                ▼
              Response returned to caller (CLI / API / event sink)
```

### 5.1 Retry & Recovery Strategy

| Scenario | Behavior |
|---|---|
| **Provider rate-limited** | Backoff with jitter, try next provider in priority order |
| **All cloud providers exhausted** | Fall back to local SLM; if that fails, mark task as `PENDING_RECOVERY` |
| **Task fails after max retries** | Mark as `FAILED`, log details, surface to user |
| **System restarts** | Worker scans for `IN_PROGRESS` tasks older than timeout → requeue |
| **Duplicate prevention** | Idempotency key checked before any side-effecting action |

---

## 6. Hierarchy and Router Interaction

```
Orchestrator
  │
  ├── "Qualify this lead" → Sales Agent
  │     │
  │     ├── Fetch lead data        → Tool (SQL query)        [Router: DETERMINISTIC]
  │     ├── Enrich from web        → Tool (API call)         [Router: DETERMINISTIC]
  │     ├── Score lead             → ML model or rules       [Router: ML]
  │     ├── Draft follow-up email  → LLM agent               [Router: LOCAL_SLM or CLOUD_LLM]
  │     └── Save results           → Tool (SQL insert)       [Router: DETERMINISTIC]
  │
  └── Return aggregated result to caller
```

**Key point:** The Task/Model Router is a *service* called by agents, not a layer they pass through. An agent says: "I need to do X with these constraints" → the router returns a callable (function, model client, or LLM client) → the agent executes it.

---

## 7. Security & Secrets Handling

### 7.1 Secrets Management
- **All secrets** (API keys, tokens) stored in `.env` file, **never committed**.
- **`.env.example`** committed with placeholder values and comments.
- **`python-dotenv`** loads secrets at startup.
- **Git:** `.gitignore` includes `.env`, `*.db`, `__pycache__/`, `.venv/`, etc.

### 7.2 Access Control (Future)
- No multi-user auth needed during dev/test phase.
- Design interfaces to accept a `user_context` parameter for future RBAC.

### 7.3 Data Safety
- No real customer PII during development — use synthetic/test data only.
- Audit log records all agent actions for traceability.

---

## 8. GitHub Workflow

### 8.1 Repository Structure (Planned)

```
agentic-crm/
├── docs/
│   ├── architecture.md          ← This document
│   ├── roadmap.md               ← Phased plan
│   └── decisions/               ← Architecture Decision Records (ADRs)
├── src/
│   ├── __init__.py
│   ├── main.py                  ← Entry point (CLI or API)
│   ├── config.py                ← Settings from env vars
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py        ← SQLite connection management
│   │   ├── migrations/          ← Schema versioning scripts
│   │   └── models.py            ← Table definitions
│   ├── core/
│   │   ├── __init__.py
│   │   ├── task.py              ← Task data model & lifecycle
│   │   ├── queue.py             ← Task queue implementation
│   │   └── worker.py            ← Background worker loop
│   ├── router/
│   │   ├── __init__.py
│   │   ├── model_router.py      ← Task/Model routing logic
│   │   └── capability.py        ← Capability level definitions
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py              ← Provider interface (ABC)
│   │   ├── manager.py           ← Provider registry & health
│   │   ├── ollama_provider.py
│   │   ├── gemini_provider.py
│   │   ├── groq_provider.py
│   │   └── ...
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── orchestrator.py      ← Grandparent orchestrator
│   │   └── sales/
│   │       ├── __init__.py
│   │       ├── agent.py         ← Sales domain agent
│   │       └── tools/           ← Sales-specific tools
│   └── crm/
│       ├── __init__.py
│       └── leads/               ← First CRM domain module
│           ├── __init__.py
│           ├── models.py
│           ├── service.py
│           └── tools.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py              ← Shared fixtures
│   ├── test_config.py
│   ├── test_queue.py
│   ├── test_router.py
│   ├── test_providers/
│   └── test_agents/
├── .env.example                 ← Placeholder secrets
├── .gitignore
├── pyproject.toml               ← Project metadata & dependencies
├── README.md
└── LICENSE
```

### 8.2 Branching Strategy
- **`main`** — stable, tested code only.
- **`dev`** — integration branch for in-progress work.
- **Feature branches** — `feature/<milestone-name>` for each roadmap milestone.
- Merge via pull request with passing tests.

### 8.3 Commit Conventions
- Conventional Commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`.
- Each commit should be atomic and buildable.

### 8.4 CI Readiness
- GitHub Actions workflow file prepared (but not activated until repo exists).
- Runs: `pytest`, linting (`ruff`), type checking (`mypy`).

---

## 9. Testing Strategy

| Level | Scope | Tools |
|---|---|---|
| **Unit** | Individual functions, router logic, provider adapters | pytest, mocks |
| **Integration** | Task lifecycle end-to-end with SQLite | pytest, in-memory SQLite |
| **Provider** | Each LLM provider adapter (mocked + optional live) | pytest, responses/httpx-mock |
| **Agent** | Orchestrator routing, domain agent decomposition | pytest, mock providers |
| **Manual/Smoke** | CLI interaction, full flow | Manual scripts, documented steps |

- **Mocking strategy:** All external API calls are mocked by default. Live provider tests are opt-in via `--run-live` flag.
- **Test data:** Synthetic CRM data (fake leads, contacts) generated by fixtures.
- **Coverage target:** 80%+ for core modules (router, queue, providers).

---

## 10. Limitations & Honest Constraints

| Constraint | Impact |
|---|---|
| **No GPU** | Local LLMs limited to small models (≤4B params). Inference will be slower (~5-15 tokens/sec on CPU). Acceptable for dev/test. |
| **16 GB RAM** | Can run one small local model + the app + SQLite comfortably. Cannot run multiple large models simultaneously. |
| **No 24/7 guarantee** | Laptop must be powered on, connected to internet, and not sleeping. True 24/7 requires a server (future phase). |
| **Free API quotas** | Subject to change without notice. System must handle sudden quota reductions gracefully. |
| **Single-machine** | No horizontal scaling during dev. Design interfaces to allow it later. |

---

## 11. Decisions Requiring Approval

| # | Decision | Options | Recommendation |
|---|---|---|---|
| D1 | Python version | 3.11 vs 3.12 vs 3.13 | 3.11+ (broad compatibility) |
| D2 | ORM vs raw SQL | SQLAlchemy Core vs raw SQL with migrations | SQLAlchemy Core (type safety, migration support, no ORM overhead) |
| D3 | Async vs sync | Full async vs sync-first | Async (`asyncio`) — needed for concurrent provider calls and background workers |
| D4 | Local LLM runtime | Ollama vs llama-cpp-python direct | Ollama (easier model management, HTTP API, separate process) |
| D5 | First CRM domain | Leads vs Contacts vs Accounts | Leads (most self-contained, clear CRUD + scoring workflow) |
| D6 | License | MIT vs Apache 2.0 | MIT (simpler, permissive) |

---

*This document will be updated as decisions are made and the system evolves.*
