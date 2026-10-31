# Agentic CRM — Architecture Document

> **Status:** Active Architecture Specification v0.2 · Multi-Agent Salesforce-Like CRM  
> **Last updated:** 2026-10-31  
> **Scope:** Multi-agent hierarchy, deterministic routing, SLM-first local execution (8GB/16GB RAM), and provider architecture.

---

## 1. System Overview

The Agentic CRM is a modular, hierarchical, event-driven CRM system inspired by enterprise platforms like Salesforce, combining deterministic Python execution with multi-tiered agent orchestration. It is designed to run locally on single Windows/Linux laptops with either 8 GB or 16 GB of RAM, adhering strictly to a **zero mandatory cloud costs** and **SLM-first** local execution philosophy while retaining graceful cloud fallback options.

### 1.1 Design Principles

| Principle | Implication |
|---|---|
| **SLM-First & Local-First** | Prioritize small language models (≤1.5B on 8GB RAM, ≤3.8B on 16GB RAM) running locally via Ollama or llama.cpp. Avoid mandatory external cloud dependencies. |
| **Agent Frugality & Tool Boundary** | Use LLM/SLM agents only where unstructured reasoning, language comprehension, or open-ended synthesis is required. CRUD operations, SQL queries, metric calculations, and validation are strictly deterministic Python tools. |
| **4-Level Hierarchy** | Work flows down a clean 4-tier chain of command: Level 1 Orchestrator → Level 2 Domain Agents → Level 3 Specialist Agents → Level 4 Sub-specialists / Deterministic Tools. |
| **Cost ceiling = $0** | All external APIs must utilize free tiers or remain zero-cost. The system never auto-escalates to paid models. |
| **Graceful Degradation** | Deterministic logic always serves as primary baseline. If cloud models quota-out or local SLMs are unavailable, tasks safely queue or degrade without data loss or crashes. |
| **Hardware-Aware Memory Budgets** | Strict memory ceilings: ≤2.2 GB model footprint for 8 GB RAM systems; ≤5.5 GB model footprint for 16 GB RAM systems; lazy model loading on CPU/GPU. |

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

## 3. Component Architecture & 4-Level CRM Hierarchy

The CRM architecture is organized into a 4-level hierarchical model (fully detailed in [`docs/CRM_AGENT_HIERARCHY.md`](CRM_AGENT_HIERARCHY.md)):

```
Level 1: Grandparent Orchestrator (Top-Level Dispatcher & Lifecycle Manager)
  │ [IMPLEMENTED: Deterministic Classifier + OpenRouter LLM Fallback]
  │
  ├──► Level 2: Sales Domain Agent (Parent) [PARTIALLY IMPLEMENTED]
  │      ├──► Level 3: Lead Management Agent [PLANNED]
  │      │      ├──► Level 4 Tools: Lead CRUD, Duplicate Detection, Phone/Email Validator
  │      │      └──► Level 4 Sub-Agent: Lead Intent Extraction SLM
  │      ├──► Level 3: Contact Management Agent [PLANNED]
  │      ├──► Level 3: Account Management Agent [PLANNED]
  │      ├──► Level 3: Opportunity Management Agent [PLANNED]
  │      └──► Level 3: Deal Management Agent [PLANNED]
  │
  ├──► Level 2: Marketing Domain Agent (Parent) [PLACEHOLDER]
  │      ├──► Level 3: Campaign Management Agent [PLANNED]
  │      ├──► Level 3: Email Marketing Agent [PLANNED]
  │      ├──► Level 3: Audience Segmentation Agent [PLANNED]
  │      ├──► Level 3: Marketing Automation Agent [PLANNED]
  │      └──► Level 3: Campaign Analytics Agent [PLANNED]
  │
  ├──► Level 2: Customer Service Domain Agent (Parent) [PLACEHOLDER]
  │      ├──► Level 3: Customer Support Agent [PLANNED]
  │      ├──► Level 3: Ticket Management Agent [PLANNED]
  │      ├──► Level 3: Ticket Classification Agent [PLANNED]
  │      ├──► Level 3: Query Resolution Agent [PLANNED]
  │      └──► Level 3: Customer Satisfaction Agent [PLANNED]
  │
  └──► Level 2: Data & Analytics Domain Agent (Parent) [PLACEHOLDER]
         ├──► Level 3: Sales Analytics Agent [PLANNED]
         ├──► Level 3: Customer Analytics Agent [PLANNED]
         ├──► Level 3: Report Generation Agent [PLANNED]
         ├──► Level 3: Sales Forecasting Agent [PLANNED]
         └──► Level 3: Business Intelligence Agent [PLANNED]

Cross-Cutting Execution & Infrastructure:
  ┌─────────────────────────────────────────────────────────┐
  │               TASK / MODEL ROUTER (Planned)              │
  │  Selects execution method per sub-task:                  │
  │  1. Deterministic Python Tools / SQL queries (Cost: $0)  │
  │  2. Local SLMs (Ollama ≤1.5B/3.8B - 8GB/16GB RAM)       │
  │  3. Free Cloud LLMs (OpenRouter/Groq/Gemini free tiers)  │
  │  Strict No-Paid-Fallback policy enforced                │
  └───────────────────────────┬─────────────────────────────┘
                              │
  ┌───────────────────────────▼─────────────────────────────┐
  │               PROVIDER MANAGER [IMPLEMENTED]            │
  │  Registry, health tracking, circuit breaker, retries    │
  │  Providers: MockProvider, OpenRouterProvider            │
  │  Planned: OllamaProvider (Local SLM), GroqProvider      │
  └───────────────────────────┬─────────────────────────────┘
                              │
  ┌───────────────────────────▼─────────────────────────────┐
  │               PERSISTENCE LAYER [IMPLEMENTED]           │
  │  SQLite database (tasks, task_queue, providers, audit)  │
  │  Future CRM Entities: leads, contacts, accounts, deals   │
  └─────────────────────────────────────────────────────────┘
```

---

## 4. Component Boundaries & Responsibilities

The system strictly delineates responsibilities across four hierarchical levels to avoid monolithic agents and unnecessary model inference. For full details on all 20 Level 3 specialist agents and schemas, see [`docs/CRM_AGENT_HIERARCHY.md`](CRM_AGENT_HIERARCHY.md).

### 4.1 Level 1: Grandparent Orchestrator
- **Status:** `IMPLEMENTED` (`src/agents/orchestrator/orchestrator.py`)
- **Responsibility:** Top-level intake from persistent queue, domain routing (`sales`, `marketing`, `customer_service`, `data`, `unknown`), overall task lifecycle management.
- **Classification Flow:** Deterministic keyword/pattern classifier first. If ambiguous, triggers optional LLM-assisted classification (OpenRouter) with strict schema validation and graceful fallback to `unknown`.

### 4.2 Level 2: Domain Parent Agents
- **Status:** Sales (`PARTIALLY IMPLEMENTED` in `src/agents/sales/agent.py`); Marketing, Customer Service, Data & Analytics (`PLACEHOLDER` in `src/agents/orchestrator/handlers.py`).
- **Responsibility:** Receive domain tasks from the Orchestrator, decompose complex business workflows into specialist sub-tasks, delegate to Level 3 Specialist Agents, and synthesize aggregated results back to Level 1.
- **Execution:** Coordinated using LangGraph StateGraphs.

### 4.3 Level 3: Specialist Child Agents (20 Total across 4 Domains)
- **Status:** `PLANNED`
- **Sales Domain (5):** Lead Management, Contact Management, Account Management, Opportunity Management, Deal Management.
- **Marketing Domain (5):** Campaign Management, Email Marketing, Audience Segmentation, Marketing Automation, Campaign Analytics.
- **Customer Service Domain (5):** Customer Support, Ticket Management, Ticket Classification, Query Resolution, Customer Satisfaction.
- **Data & Analytics Domain (5):** Sales Analytics, Customer Analytics, Report Generation, Sales Forecasting, Business Intelligence.
- **Responsibility:** Deep, domain-specific execution. Each specialist orchestrates a narrowly defined business lifecycle using Level 4 tools and sub-specialist SLMs.

### 4.4 Level 4: Sub-Specialists vs. Deterministic Tools
- **Deterministic Python Tools (Primary Baseline):**
  - **Rule:** Simple CRUD, database queries, calculations, schema validations, and formatting **must NEVER be assigned to an LLM/SLM**.
  - Implemented as pure Python functions or SQL queries (`lead_repository.insert()`, `calculate_pipeline_velocity()`).
- **Sub-Specialist Agents (Cognitive Tasks Only):**
  - Invoked only for unstructured reasoning, sentiment analysis, email synthesis, or entity extraction.
  - Powered by local SLMs (e.g. Qwen2.5-1.5B or Phi-3-mini) through the Provider Manager.

### 4.5 Hardware Profiling & Memory Budgets (8GB vs 16GB RAM)
To ensure reliable operation on standard laptops without requiring a dedicated GPU or crashing system memory:
- **8 GB RAM Profile:**
  - Operating System & Agent CRM Core: ~4.5 GB to 5.0 GB
  - Model Memory Ceiling: **≤2.2 GB**
  - Target Models: Qwen2.5-1.5B (Q4_K_M ~1.1 GB) or Llama-3.2-1B (Q4_K_M ~0.9 GB)
  - Strategy: Strict single-model concurrency, lazy loading into RAM only during inference.
- **16 GB RAM Profile:**
  - Operating System & Agent CRM Core: ~6.0 GB to 7.0 GB
  - Model Memory Ceiling: **≤5.5 GB**
  - Target Models: Phi-3-mini 3.8B (Q4_K_M ~2.4 GB) or Qwen2.5-3B (Q4_K_M ~2.0 GB)
  - Strategy: Fast local inference on CPU/iGPU, background model pre-warming.

### 4.6 Task / Model Router
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

### 4.7 Provider Manager
- **Registry pattern:** Each provider (Gemini, Groq, Ollama, etc.) is a plugin implementing a common interface.
- **Tracks per-provider:**
  - Remaining quota (requests/day, tokens/minute)
  - Current rate-limit status
  - Health (up/down/degraded)
  - Last error and backoff timer
- **Circuit breaker:** After N consecutive failures, mark provider as "down" for a cooldown period.
- **Strict policy:** A provider's `is_paid` flag is checked before every call. Paid providers are **never** selected automatically.

### 4.8 Persistence Layer
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
