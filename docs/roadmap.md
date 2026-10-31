# Agentic CRM — Development Roadmap

> **Status:** Active — Phases 1, 2 (partial), & 3 complete, Phase 4 (Agent Hierarchy) next  
> **Last updated:** 2026-10-31  
> **Approach:** Incremental, MVP-first. Each phase produces tested, working software.

---

## Milestone Status Summary

- **COMPLETED**:
  - **Phase 1 — Project Foundation**:
    - Milestone 1.1: Project Scaffold & Configuration ✅
    - Milestone 1.2: Database & Migrations ✅
    - Milestone 1.3: Task Model & Queue ✅
  - **Phase 2 — Provider Infrastructure**:
    - Milestone 2.1: Provider Interface & Manager ✅
  - **Phase 3 — LangGraph Foundation**:
    - Milestone 3.1: LangGraph Core & State Patterns ✅
    - Milestone 3.2: Execution Topologies (Branching, Loops, Parallel) ✅
    - Milestone 3.3: Provider & Task Integration ✅
- **CURRENT**:
  - Phase 3 complete. Preparing for Phase 4 (Agent Hierarchy).
- **NEXT**:
  - **Phase 4 — Agent Hierarchy**:
    - Milestone 4.1: Grandparent Orchestrator Graph
    - Milestone 4.2: Sales Domain Agent Sub-Graph (Stub)
    - Milestone 4.3: CLI Intake Layer
- **FUTURE (Re-sequenced)**:
  - **Phase 5 — Concrete Providers & Model Router**: Ollama, Gemini, Groq, Model Router (to be plugged into the LangGraph execution layer)
  - **Phase 6 — Reliability & Recovery**: Worker loop, crash recovery, idempotency, audit logging
  - **Phase 7 — First CRM Feature**: Leads CRUD, rule-based scoring, Sales Agent integration
  - **Phase 8 — API & Scheduling**: FastAPI REST layer, APScheduler

---

## Phase Overview

```mermaid
gantt
    title Agentic CRM — Phased Roadmap
    dateFormat  YYYY-MM-DD
    axisFormat  %b %d

    section Phase 1 — Foundation (DONE)
    Scaffold, DB, Task Queue        :done, p1, 2026-10-22, 2026-10-22

    section Phase 2 — Provider Base (DONE)
    Provider interface & manager    :done, p2a, 2026-10-31, 2026-10-31

    section Phase 3 — LangGraph (DONE)
    Core, Topologies, Integration   :done, p3, 2026-10-31, 2026-10-31

    section Phase 4 — Agent Hierarchy (NEXT)
    Orchestrator & Domain Agents    :active, p4, 2026-10-31, 5d

    section Phase 4 — Agent Hierarchy
    Orchestrator & Domain Agents    :p4, after p3, 5d

    section Phase 5 — Providers & Router
    Ollama, Cloud, Model Router     :p5, after p4, 5d

    section Phase 6 — Reliability
    Worker, Idempotency, Audit      :p6, after p5, 5d

    section Phase 7 — CRM Leads
    Leads CRUD, Scoring, Integration:p7, after p6, 5d

    section Phase 8 — API & Scheduling
    FastAPI & APScheduler           :p8, after p7, 5d
```

---

## Phase 1 — Project Foundation

**Goal:** Bootable project with config, database, and task persistence.

### Milestone 1.1 — Project Scaffold & Configuration
| Item | Detail |
|---|---|
| **Work** | Create `pyproject.toml`, directory structure per architecture doc, `.gitignore`, `.env.example`, `README.md`, `config.py` (loads env vars via `python-dotenv`) |
| **Acceptance** | `pip install -e .` succeeds; `python -m src.config` prints loaded config (with no real secrets); `.gitignore` excludes `.env`, `*.db`, `__pycache__/`, `.venv/` |
| **Tests** | `test_config.py` — config loads defaults when no `.env` present; missing required vars raise clear errors |
| **Dependencies** | None (first milestone) |

### Milestone 1.2 — Database & Migrations
| Item | Detail |
|---|---|
| **Work** | SQLite connection manager (`aiosqlite`), initial schema (tasks, task_queue, providers, audit_log), migration runner (numbered SQL scripts) |
| **Acceptance** | Running migrations creates all tables; schema can be inspected; re-running is idempotent |
| **Tests** | `test_database.py` — tables created correctly, migration idempotency, connection open/close |
| **Dependencies** | Milestone 1.1 |

### Milestone 1.3 — Task Model & Queue
| Item | Detail |
|---|---|
| **Work** | Task dataclass/Pydantic model, enqueue/dequeue functions, status transitions (PENDING → IN_PROGRESS → COMPLETED/FAILED/RETRY), priority support |
| **Acceptance** | Tasks can be created, enqueued, dequeued by priority, status-transitioned, and persisted across restarts |
| **Tests** | `test_task.py`, `test_queue.py` — CRUD, ordering, status transitions, persistence after simulated restart |
| **Dependencies** | Milestone 1.2 |

---

## Phase 2 — Provider Infrastructure

**Goal:** Establish provider abstraction, registry, health tracking, and circuit breakers.

### Milestone 2.1 — Provider Interface & Manager ✅
| Item | Detail |
|---|---|
| **Work** | `BaseProvider` ABC (common interface: `generate()`, `health_check()`, `get_quota()`), `ProviderManager` (registry, health tracking, circuit breaker, rate-limit backoff), `is_paid` flag enforcement |
| **Acceptance** | Providers can be registered, health-checked; paid providers are never auto-selected; circuit breaker triggers after N failures |
| **Tests** | `test_provider_base.py`, `test_provider_manager.py` — mock providers, paid-rejection, circuit breaker, fallback ordering (224 tests passing) |
| **Dependencies** | Milestone 1.3 |
| **Status** | **COMPLETED** (Commit `79b3866`) |

> **Strategic Realignment Note:** Milestones 2.2 (Ollama), 2.3 (Cloud Providers), and 2.4 (Model Router) are deferred to **Phase 5**. The existing `ProviderManager` and `BaseProvider` ABC provide sufficient mock/test support to build and validate the LangGraph orchestration layer without needing live LLM APIs.

---

## Phase 3 — LangGraph Foundation (NEXT)

**Goal:** Establish state-machine graph orchestration patterns using LangGraph before building domain agents.

### Milestone 3.1 — LangGraph Core & State Patterns
| Item | Detail |
|---|---|
| **Work** | Add `langgraph` dependency; define typed State schemas; build core execution pattern: `State -> Node -> Graph -> Edge -> Compile -> Invoke` |
| **Acceptance** | Basic graph compiles, accepts state input, executes sequential nodes deterministically, returns modified state |
| **Tests** | `tests/test_graph_core.py` — state schema validation, node execution, state transitions, compilation |
| **Dependencies** | Milestone 2.1 |
| **Status** | **NEXT MILESTONE** |

### Milestone 3.2 — Execution Topologies (Branching, Loops & Parallel)
| Item | Detail |
|---|---|
| **Work** | Implement conditional routing edges, iterative loops with termination conditions, and parallel node execution patterns in LangGraph |
| **Acceptance** | Graphs dynamically route based on state predicates; loops terminate safely; parallel branches aggregate state cleanly |
| **Tests** | `tests/test_graph_topologies.py` — conditional routing, cycle detection/termination, parallel fan-out/fan-in |
| **Dependencies** | Milestone 3.1 |

### Milestone 3.3 — Provider & Task Integration ✅
| Item | Detail |
|---|---|
| **Work** | Integrate graph execution with existing `ProviderManager` (using mock/fake providers) and CRM `Task` data models |
| **Acceptance** | Graph nodes invoke provider abstractions via `ProviderManager`; task state maps to/from LangGraph state; TaskExecutor coordinates lifecycle transitions |
| **Tests** | `tests/test_task_graph.py`, `tests/test_task_executor.py` — graph invocation with MockProvider, task lifecycle mapping (245 tests passing) |
| **Dependencies** | Milestone 3.2 |
| **Status** | **COMPLETED** |

---

## Phase 4 — Agent Hierarchy

**Goal:** Working orchestrator → domain agent → tool chain implemented via LangGraph.

### Milestone 4.1 — Grandparent Orchestrator ✅
| Item | Detail |
|---|---|
| **Work** | Orchestrator graph: receives tasks from queue, classifies domain (rule-based deterministic classifier), delegates to decoupled domain handlers (sales, marketing, customer_service, data, unknown), tracks lifecycle, handles fallback |
| **Acceptance** | Orchestrator correctly routes tasks to their designated domain handler and unknown tasks to general fallback handler |
| **Tests** | `test_orchestrator.py` — classification, routing, domain handlers, GrandparentOrchestrator sync and async execution (37 focused tests; 282 total regression tests passing) |
| **Dependencies** | Phase 3 (LangGraph Foundation) |
| **Status** | **COMPLETED** |

### Milestone 4.2 — Sales Domain Agent Foundation ✅
| Item | Detail |
|---|---|
| **Work** | `SalesDomainAgent` sub-graph: receives delegated sales tasks from Grandparent Orchestrator, classifies sales subdomain (`lead_management`, `opportunity_management`, `deal_management`, `general_sales`), executes decoupled subdomain handlers, aggregates results |
| **Acceptance** | Sales Agent receives task, routes to designated subdomain handler, returns structured result to orchestrator; Grandparent Orchestrator integrates delegation seamlessly |
| **Tests** | `test_sales_agent.py` — classification, subdomain routing, handler execution, Grandparent integration (39 focused tests; 321 total regression tests passing) |
| **Dependencies** | Milestone 4.1 |
| **Status** | **COMPLETED** |

### Milestone 4.3 — CLI Intake Layer ✅
| Item | Detail |
|---|---|
| **Work** | Simple CLI (`argparse`) that accepts a task description, creates and enqueues a Task in the persistent SQLite queue, runs the Grandparent Orchestrator graph pipeline, and prints the result |
| **Acceptance** | `python -m src.main "Qualify lead John Doe"` → task created → routed → result printed |
| **Tests** | `test_cli.py` — CLI parsing, task creation, end-to-end execution, text & JSON formatting (13 focused tests; 334 total regression tests passing) |
| **Dependencies** | Milestone 4.2 |
| **Status** | **COMPLETED** |

---

## Phase 5 — Concrete Providers & Routing (IN PROGRESS)

**Goal:** Integrate real LLM providers into the agent hierarchy and implement routing from deterministic methods up to cloud models.

### Milestone 5.1 — OpenRouter Provider
| Item | Detail |
|---|---|
| **Work** | `OpenRouterProvider` implementing `BaseProvider` and integrated into `ProviderManager`. Communicates with OpenRouter OpenAI-compatible completions API, reads credentials from env/settings, configurable free model (`nvidia/nemotron-3.5-lightning:free`), token & latency tracking, availability check, key sanitization. |
| **Acceptance** | `OpenRouterProvider` cleanly generates completions, handles rate limits/errors gracefully, redacts API keys in errors, integrates with `ProviderManager` health & circuit breaker. |
| **Tests** | `test_openrouter_provider.py` — mocked HTTP responses for success, auth failure, rate-limit (429), server error (500), timeout, network errors, circuit breaker integration, secret protection (18 focused tests; 352 total regression tests passing) |
| **Dependencies** | Milestone 2.1 |
| **Status** | **COMPLETED** |

### Milestone 5.2 — LLM-Assisted Orchestrator Classification (OpenRouter) (NEXT)
| Item | Detail |
|---|---|
| **Work** | Integrate optional LLM-assisted domain classification in `GrandparentOrchestrator` when deterministic classification is uncertain. Connects via existing `ProviderManager` / `OpenRouterProvider` abstraction using configured model (`nvidia/nemotron-3.5-lightning:free`). Deterministic classification remains the primary first step. Validates LLM output into strict domain set (`sales`, `marketing`, `customer_service`, `data`, `unknown`). Safe degradation to `unknown` or deterministic result on provider errors, rate limits, or invalid responses. |
| **Acceptance** | High-confidence deterministic tasks route without calling the LLM; ambiguous tasks leverage LLM classification; invalid outputs or provider outages gracefully fall back without breaking the orchestrator; orchestrator remains provider-agnostic. |
| **Tests** | `test_orchestrator_llm.py` — deterministic precedence, LLM fallback invocation, valid domain parsing, invalid domain rejection, provider failure fallback, missing key safety, Sales routing compatibility. |
| **Dependencies** | Milestone 5.1, Milestone 4.1 |
| **Status** | **NEXT** |

### Milestone 5.3 — Local Provider (Ollama) / Additional Providers (Groq)
| Item | Detail |
|---|---|
| **Work** | Additional concrete providers (`OllamaProvider`, `GroqProvider`) implementing `BaseProvider`, local/cloud execution, rate limit and health checks. |
| **Acceptance** | Providers report healthy when running, graceful degradation when unavailable. |
| **Tests** | Mocked unit tests and optional live verification tests. |
| **Dependencies** | Milestone 5.1 |
| **Status** | **DEFERRED** |

### Milestone 5.4 — Task / Model Router
| Item | Detail |
|---|---|
| **Work** | `ModelRouter` with capability levels (DETERMINISTIC, ML, LOCAL_SLM, CLOUD_LLM, CLOUD_LLM_CAPABLE), routing logic that queries `ProviderManager` for availability, fallback chain, strict no-paid policy |
| **Acceptance** | Router selects lowest-cost available method; falls back correctly when providers are down; never selects a paid provider; deterministic tasks bypass LLM entirely |
| **Tests** | `test_model_router.py` — routing decisions with various provider availability scenarios, capability matching, paid-provider rejection |
| **Dependencies** | Milestones 5.1–5.3 |
| **Status** | **DEFERRED** |

---

## Phase 6 — Reliability & Recovery

**Goal:** The system can survive crashes, retries, and provider outages without data loss or duplicate actions.

### Milestone 6.1 — Worker Loop & Recovery
| Item | Detail |
|---|---|
| **Work** | Async worker loop that polls the task queue, processes tasks via orchestrator, handles timeouts, requeues stale `IN_PROGRESS` tasks on startup |
| **Acceptance** | Worker processes queued tasks; simulated crash → restart → stale tasks are requeued and reprocessed |
| **Tests** | `test_worker.py` — processing, timeout, restart recovery |
| **Dependencies** | Milestone 4.3 |

### Milestone 6.2 — Idempotency & Deduplication
| Item | Detail |
|---|---|
| **Work** | Idempotency key generation per task, dedup check before side-effecting actions, idempotency record table |
| **Acceptance** | Replaying a task with the same idempotency key does not produce duplicate side effects |
| **Tests** | `test_idempotency.py` — duplicate detection, key generation, replay safety |
| **Dependencies** | Milestone 6.1 |

### Milestone 6.3 — Audit Logging
| Item | Detail |
|---|---|
| **Work** | Structured audit log (who/what/when/why) for all agent decisions, provider calls, and task state changes |
| **Acceptance** | Every task execution produces a traceable audit trail in the database |
| **Tests** | `test_audit.py` — log creation, queryability, completeness |
| **Dependencies** | Milestone 6.2 |

---

## Phase 7 — First CRM Feature: Leads

**Goal:** A real CRM capability — managing and scoring leads — wired through the full agent hierarchy.

### Milestone 7.1 — Leads Module (CRUD)
| Item | Detail |
|---|---|
| **Work** | `Lead` model (name, email, company, source, status, score, notes, timestamps), CRUD service, database table and migration |
| **Acceptance** | Leads can be created, read, updated, deleted, listed with filters |
| **Tests** | `test_leads_crud.py` — full CRUD, validation, filtering |
| **Dependencies** | Milestone 6.3 |

### Milestone 7.2 — Lead Scoring (Rules-Based)
| Item | Detail |
|---|---|
| **Work** | Rule-based lead scoring engine (configurable criteria: company size, source, engagement), score calculation, score persistence |
| **Acceptance** | New or updated leads get a score; scoring rules can be configured without code changes |
| **Tests** | `test_lead_scoring.py` — various lead profiles, edge cases, config changes |
| **Dependencies** | Milestone 7.1 |

### Milestone 7.3 — Sales Agent + Leads Integration
| Item | Detail |
|---|---|
| **Work** | Wire Sales Agent to use Leads tools (create, score, qualify), orchestrator routes lead-related tasks to Sales Agent, optional LLM-powered lead summary |
| **Acceptance** | `"Create lead: John Doe, ACME Corp"` → Lead created, scored, result returned via CLI |
| **Tests** | `test_sales_leads_integration.py` — end-to-end with mock providers |
| **Dependencies** | Milestones 7.1, 7.2, 4.2 |

---

## Phase 8 — API & Scheduling (Future)

**Goal:** External access and time-based automation.

### Milestone 8.1 — FastAPI REST Layer
| Item | Detail |
|---|---|
| **Work** | REST endpoints for tasks and leads, OpenAPI documentation, async handlers |
| **Acceptance** | CRUD operations via HTTP, Swagger UI accessible |
| **Tests** | `test_api.py` — endpoint tests with `httpx` |
| **Dependencies** | Phase 7 |

### Milestone 8.2 — Scheduled Tasks
| Item | Detail |
|---|---|
| **Work** | APScheduler integration, cron-style task definitions, scheduled lead re-scoring |
| **Acceptance** | A scheduled task runs at defined intervals; missed schedules are caught up on restart |
| **Tests** | `test_scheduler.py` — scheduling, execution, recovery |
| **Dependencies** | Milestone 8.1 |

---

## Future Phases (Not Yet Planned in Detail)

| Phase | Scope |
|---|---|
| **7** | Contacts & Accounts modules, relationship linking |
| **8** | Service Agent — ticket/case management |
| **9** | Marketing Agent — campaign management, email templates |
| **10** | RAG / Semantic search with vector DB |
| **11** | Web dashboard UI |
| **12** | Multi-user auth and RBAC |
| **13** | Deployment to always-on server for 24/7 operation |

---

## Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Free API quotas reduced or eliminated without notice | High | High | Multiple providers, local fallback, graceful degradation, task queuing |
| R2 | Rate limiting causes task failures | High | Medium | Exponential backoff with jitter, circuit breaker, provider rotation |
| R3 | Duplicate actions after retry (e.g., duplicate emails) | Medium | High | Idempotency keys, dedup checks before side effects |
| R4 | Local SLM too slow or low-quality on CPU | Medium | Medium | Use smallest effective models; reserve LLM for tasks that truly need it; accept slower dev/test performance |
| R5 | SQLite concurrency limits under load | Low (dev) | Medium | Single-writer design; migrate to PostgreSQL when needed |
| R6 | Laptop not suitable for 24/7 operation | Certain | Medium | Document limitation; plan for server deployment in Phase 13; don't promise 24/7 until infra exists |
| R7 | Security — API keys leaked in code | Medium | High | `.env` + `.gitignore` + pre-commit hooks + code review discipline |
| R8 | Scope creep — trying to build all of Salesforce | Medium | High | Strict phase gating; each phase requires passing tests before the next begins |
| R9 | Provider API changes break adapters | Medium | Medium | Adapter pattern isolates changes; version-pin SDK dependencies |
| R10 | Data loss from SQLite file corruption | Low | High | Regular backups (manual initially); WAL mode for crash safety |

---

## Next Implementation Milestone: Phase 4 — Agent Hierarchy

**The next implementation step is Phase 4 — Agent Hierarchy (Milestones 4.1–4.3):**

1. **Milestone 4.1:** Grandparent Orchestrator (Orchestrator graph routing tasks to domain agent sub-graphs).
2. **Milestone 4.2:** Sales Domain Agent (Sub-graph decomposing domain tasks into tool/specialist calls).
3. **Milestone 4.3:** CLI Intake Layer (Accepting tasks via CLI and triggering orchestrator execution).

**Why prioritize this next:**
- Phase 3 LangGraph Foundation is complete with full graph execution, topologies, and task/provider wiring.
- The Agent Hierarchy can now be built on top of the established LangGraph state-machine patterns.
- Keeps cost at $0 using deterministic mock providers before connecting live models in Phase 5.

---

*This roadmap will be updated as phases are completed and new requirements emerge.*
