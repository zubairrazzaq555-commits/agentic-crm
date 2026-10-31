# Agentic CRM — Complete Agent Hierarchy & Architecture Audit

**Audit Date:** 2026-10-31  
**Repository:** `agentic-crm`  
**Current Milestone:** Completed Milestone 5.2 (`3d31dda`)  
**Scope of Audit:** Source code, tests, schemas, configuration, architecture documentation, and development log.

---

## Executive Summary

This document provides a factual, code-verified audit of the agent architecture in the Agentic CRM project as of Milestone 5.2. Every finding in this audit reflects the actual state of the Python code in the repository.

### Summary of Implementation Reality
- **Grandparent Orchestrator:** **IMPLEMENTED**. Possesses a compiled LangGraph state machine, dual-mode classification (deterministic keyword scoring as primary + OpenRouter LLM fallback via `ProviderManager`), and conditional routing to 5 domain handler nodes.
- **Sales Domain Agent:** **PARTIALLY IMPLEMENTED (FOUNDATION ONLY)**. Implemented as a LangGraph state machine with deterministic subdomain classification routing to 4 subdomain handler nodes. However, all 4 subdomain handlers are **pure placeholder stubs** returning static dictionaries. No CRM database entities (leads, opportunities, accounts) or child specialist agents exist yet.
- **Other Domain Agents (Marketing, Customer Service, Data):** **NOT IMPLEMENTED**. Only lightweight handler stubs exist inside the orchestrator (`marketing_handler_node`, `customer_service_handler_node`, `data_handler_node`). No dedicated domain agent classes, graphs, or packages exist for them.
- **Child / Specialist Agents:** **NOT IMPLEMENTED**. No child agents (e.g. Lead Scoring Agent, Email Drafter, Meeting Summarizer) exist anywhere in the codebase.
- **CRM Functional Logic / CRUD:** **NOT IMPLEMENTED**. The database contains only a `tasks` queue table. There are no tables, schemas, or business functions for leads, contacts, deals, or tickets.
- **LLM Usage:** **RESTRICTED TO CLASSIFICATION ONLY**. LLM integration exists exclusively in `src/agents/orchestrator/classifier.py` to classify ambiguous task descriptions. No agent currently uses an LLM to generate, reason over, or execute business actions.

---

## PART 1 — Complete Agent Hierarchy

### A. Verified Implemented Hierarchy (Actual Code)

```
Grandparent Orchestrator (src/agents/orchestrator/orchestrator.py: GrandparentOrchestrator)
 │
 ├── Classification Layer (src/agents/orchestrator/classifier.py)
 │    ├── Deterministic Keyword Classifier (classify_domain_confidence: lines 98–170) [PRIMARY]
 │    └── LLM Fallback Classifier (llm_classify_domain: lines 275–303) [FALLBACK via OpenRouter]
 │
 ├── Sales Domain Handler (src/agents/orchestrator/handlers.py: sales_handler_node)
 │    │
 │    └── Sales Domain Agent (src/agents/sales/agent.py: SalesDomainAgent) [FOUNDATION ONLY]
 │         │
 │         ├── Sales Subdomain Classifier (src/agents/sales/classifier.py: classify_sales_task) [DETERMINISTIC]
 │         │
 │         ├── Lead Management Handler (src/agents/sales/handlers.py: lead_management_handler) [STUB]
 │         ├── Opportunity Management Handler (src/agents/sales/handlers.py: opportunity_management_handler) [STUB]
 │         ├── Deal Management Handler (src/agents/sales/handlers.py: deal_management_handler) [STUB]
 │         └── General Sales Handler (src/agents/sales/handlers.py: general_sales_handler) [STUB]
 │
 ├── Marketing Domain Handler (src/agents/orchestrator/handlers.py: marketing_handler_node) [STUB]
 ├── Customer Service Domain Handler (src/agents/orchestrator/handlers.py: customer_service_handler_node) [STUB]
 ├── Data Domain Handler (src/agents/orchestrator/handlers.py: data_handler_node) [STUB]
 └── Unknown Fallback Handler (src/agents/orchestrator/handlers.py: unknown_handler_node) [STUB]
```

### B. Planned Hierarchy (Architecture Document & Roadmap)

```
Grandparent Orchestrator
 ├── Sales Domain Agent (Parent)
 │    ├── Lead Management Specialist Agent (Child) [PLANNED]
 │    │    └── Lead CRUD & Scoring Tools (Deterministic Python) [PLANNED]
 │    ├── Opportunity Management Specialist Agent (Child) [PLANNED]
 │    └── Deal Management Specialist Agent (Child) [PLANNED]
 │
 ├── Marketing Domain Agent (Parent) [PLANNED]
 │    ├── Campaign Specialist Agent (Child) [PLANNED]
 │    └── Content / Email Drafter Agent (Child / LLM-assisted) [PLANNED]
 │
 ├── Customer Service Domain Agent (Parent) [PLANNED]
 │    ├── Ticket Triage & Routing Specialist Agent (Child) [PLANNED]
 │    └── Inquiry Resolution Agent (Child) [PLANNED]
 │
 ├── Data Domain Agent (Parent) [PLANNED]
 │    ├── ETL & Sync Tool / Agent (Child) [PLANNED]
 │    └── Data Cleansing & Deduplication Tool (Deterministic) [PLANNED]
 │
 └── Task / Model Router (Cross-cutting Utility) [PLANNED - Milestone 5.4]
```

---

## PART 2 — Agent Inventory

| Agent / Component Name | Hierarchy Level | Business Domain | Core Responsibilities | Tasks It Can Execute | Tools / Functions Used | Source File & Class/Function Names | Implementation Status | Intelligence Type |
|---|---|---|---|---|---|---|---|---|
| **Grandparent Orchestrator** | Top-Level Orchestrator (Grandparent) | Cross-domain CRM routing | Ingests tasks from queue/CLI, classifies business domain, manages top-level execution lifecycle, delegates to domain handlers | Any submitted CRM task | LangGraph StateGraph, `classify_domain_confidence`, `llm_classify_domain`, `ProviderManager` | [`src/agents/orchestrator/orchestrator.py`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/orchestrator/orchestrator.py): `GrandparentOrchestrator`, `create_orchestrator_graph` | **IMPLEMENTED** | Hybrid: Deterministic Keyword Classifier (Primary) + OpenRouter LLM (`nvidia/nemotron-3.5-lightning:free`) Fallback |
| **Domain Classifier Node** | Sub-component of Orchestrator | Classification | Evaluates keyword scores across domains; checks ambiguity; triggers LLM when uncertain; normalizes outputs to allowed set | Domain categorization | `_tokenize`, `classify_domain_confidence`, `_parse_llm_domain`, `OpenRouterProvider.generate` | [`src/agents/orchestrator/classifier.py`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/orchestrator/classifier.py): `classifier_node`, `create_classifier_node`, `llm_classify_domain` | **IMPLEMENTED** | Hybrid: Deterministic rules + LLM fallback |
| **Sales Domain Handler** | Orchestrator Node | Sales | Dispatches sales domain tasks to `SalesDomainAgent`; captures sales agent execution result | Sales tasks routed by orchestrator | `SalesDomainAgent.execute()` | [`src/agents/orchestrator/handlers.py`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/orchestrator/handlers.py): `sales_handler_node` (lines 33–57) | **IMPLEMENTED** | Deterministic Python dispatch |
| **Marketing Domain Handler** | Orchestrator Node | Marketing | Placeholder node for marketing tasks | Any task classified as marketing | Static dictionary constructor (`_build_delegation_payload`) | [`src/agents/orchestrator/handlers.py`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/orchestrator/handlers.py): `marketing_handler_node` (lines 60–74) | **STUB / PLACEHOLDER** | Deterministic static stub |
| **Customer Service Domain Handler** | Orchestrator Node | Customer Service | Placeholder node for support / customer service tasks | Any task classified as customer service | Static dictionary constructor (`_build_delegation_payload`) | [`src/agents/orchestrator/handlers.py`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/orchestrator/handlers.py): `customer_service_handler_node` (lines 77–91) | **STUB / PLACEHOLDER** | Deterministic static stub |
| **Data Domain Handler** | Orchestrator Node | Data | Placeholder node for data import, export, and cleanup tasks | Any task classified as data | Static dictionary constructor (`_build_delegation_payload`) | [`src/agents/orchestrator/handlers.py`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/orchestrator/handlers.py): `data_handler_node` (lines 94–108) | **STUB / PLACEHOLDER** | Deterministic static stub |
| **Unknown Fallback Handler** | Orchestrator Node | Fallback | Terminal node for unclassifiable or failed tasks | Unrecognized or unclassifiable tasks | Static dictionary constructor (`_build_delegation_payload`) | [`src/agents/orchestrator/handlers.py`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/orchestrator/handlers.py): `unknown_handler_node` (lines 111–125) | **IMPLEMENTED** | Deterministic static stub |
| **Sales Domain Agent** | Domain Coordinator (Parent) | Sales | Ingests sales tasks, classifies subdomain, routes to subdomain handlers | Sales domain tasks | LangGraph StateGraph, `classify_sales_task`, subdomain handler functions | [`src/agents/sales/agent.py`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/sales/agent.py): `SalesDomainAgent`, `create_sales_agent_graph` | **PARTIALLY IMPLEMENTED (Foundation only)** | Deterministic Python routing (no LLM) |
| **Sales Subdomain Classifier** | Sub-component of Sales Agent | Sales subdomain categorization | Classifies sales task into `lead_management`, `opportunity_management`, `deal_management`, or `general_sales` | Sales subdomain classification | `_tokenize`, `classify_sales_task` | [`src/agents/sales/classifier.py`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/sales/classifier.py): `classify_sales_task`, `sales_classifier_node` | **IMPLEMENTED** | Deterministic keyword / prefix matching |
| **Lead Management Handler** | Subdomain Handler | Sales: Leads | Placeholder handler for lead management tasks | Tasks classified into `lead_management` | Static dictionary constructor (`_build_handler_result`) | [`src/agents/sales/handlers.py`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/sales/handlers.py): `lead_management_handler` (lines 33–46) | **STUB / PLACEHOLDER** | Deterministic static stub |
| **Opportunity Management Handler** | Subdomain Handler | Sales: Opportunities | Placeholder handler for opportunity pipeline tasks | Tasks classified into `opportunity_management` | Static dictionary constructor (`_build_handler_result`) | [`src/agents/sales/handlers.py`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/sales/handlers.py): `opportunity_management_handler` (lines 49–62) | **STUB / PLACEHOLDER** | Deterministic static stub |
| **Deal Management Handler** | Subdomain Handler | Sales: Deals | Placeholder handler for quotes, contracts, and deals | Tasks classified into `deal_management` | Static dictionary constructor (`_build_handler_result`) | [`src/agents/sales/handlers.py`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/sales/handlers.py): `deal_management_handler` (lines 65–78) | **STUB / PLACEHOLDER** | Deterministic static stub |
| **General Sales Handler** | Subdomain Handler | Sales: General | Placeholder handler for unclassified or broad sales operations | Tasks falling back to `general_sales` | Static dictionary constructor (`_build_handler_result`) | [`src/agents/sales/handlers.py`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/sales/handlers.py): `general_sales_handler` (lines 81–94) | **STUB / PLACEHOLDER** | Deterministic static stub |

---

## PART 3 — CRM Functional Coverage Audit

Below is the verified status of all core CRM functional areas across the repository.

### Sales Domain
| CRM Capability | Status | Detailed Code Evidence |
|---|---|---|
| **Lead Management** | **PARTIALLY IMPLEMENTED (Routing only)** | Keyword recognition in `DOMAIN_KEYWORDS["sales"]` and `SALES_CATEGORY_KEYWORDS["lead_management"]`. Dispatches to `lead_management_handler` ([`src/agents/sales/handlers.py:33`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/sales/handlers.py#L33)). **No lead database table, schema, model, or CRUD operations exist.** Scheduled for Phase 7 (Milestone 7.1). |
| **Lead Qualification & Scoring** | **PLANNED** | No qualification rules, scoring algorithms, or models implemented. Target milestone: Phase 7 (Milestones 7.2 & 7.3). |
| **Lead Assignment** | **PLANNED** | Not implemented. |
| **Contact Management** | **NOT IMPLEMENTED** | No tables, models, or handlers exist for Contacts. |
| **Account Management** | **NOT IMPLEMENTED** | No tables, models, or handlers exist for Accounts/Companies. |
| **Opportunity Management** | **PARTIALLY IMPLEMENTED (Routing only)** | Routing keyword matching in `SALES_CATEGORY_KEYWORDS["opportunity_management"]`; routes to placeholder `opportunity_management_handler` ([`src/agents/sales/handlers.py:49`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/sales/handlers.py#L49)). No stage tracking, pipelines, or database schemas. |
| **Deal Management** | **PARTIALLY IMPLEMENTED (Routing only)** | Routing keyword matching in `SALES_CATEGORY_KEYWORDS["deal_management"]`; routes to placeholder `deal_management_handler` ([`src/agents/sales/handlers.py:65`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/sales/handlers.py#L65)). No contract, quote, or pricing logic. |
| **Sales Pipeline Management** | **NOT IMPLEMENTED** | No pipeline states, stages, or transition logic. |
| **Follow-ups** | **NOT IMPLEMENTED** | No scheduling, reminders, or follow-up task generators. |
| **Sales Forecasting** | **NOT IMPLEMENTED** | No calculation, ML, or projection logic. |
| **Sales Reporting** | **PARTIALLY IMPLEMENTED (Routing only)** | Dispatched to `general_sales_handler` ([`src/agents/sales/handlers.py:81`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/sales/handlers.py#L81)) as a stub string. No aggregation or metrics code. |

### Marketing Domain
| CRM Capability | Status | Detailed Code Evidence |
|---|---|---|
| **Campaign Management** | **NOT IMPLEMENTED** | Only keyword detection in Orchestrator classifier. Dispatches to `marketing_handler_node` ([`src/agents/orchestrator/handlers.py:60`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/orchestrator/handlers.py#L60)) which returns a static stub dictionary. No Marketing Agent exists. |
| **Email Marketing** | **NOT IMPLEMENTED** | No email drafting, SMTP integration, or templating logic. |
| **Audience Segmentation** | **NOT IMPLEMENTED** | No segmentation filters or criteria logic. |
| **Marketing Automation** | **NOT IMPLEMENTED** | No automation triggers or drip sequence logic. |
| **Lead Generation** | **NOT IMPLEMENTED** | No web forms, scrapers, or intake parsers. |
| **Campaign Analytics** | **NOT IMPLEMENTED** | No metrics or conversion tracking. |

### Customer Service Domain
| CRM Capability | Status | Detailed Code Evidence |
|---|---|---|
| **Customer Support** | **NOT IMPLEMENTED** | Only keyword detection in Orchestrator classifier. Dispatches to `customer_service_handler_node` ([`src/agents/orchestrator/handlers.py:77`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/orchestrator/handlers.py#L77)) which returns a static stub dictionary. No Customer Service Agent exists. |
| **Ticket Management** | **NOT IMPLEMENTED** | No ticket tables, schemas, status lifecycle, or CRUD. |
| **Ticket Classification & Assignment**| **PARTIALLY IMPLEMENTED (Domain routing only)** | Support keywords ("ticket", "complaint", "refund", "inquiry") route to customer service domain at the top-level orchestrator. No individual ticket assignment or priority triage exists. |
| **Customer Queries** | **NOT IMPLEMENTED** | No conversational inquiry handlers. |
| **Customer Interaction History** | **NOT IMPLEMENTED** | No activity logs, message threads, or timeline storage. |
| **Customer Satisfaction Analysis** | **NOT IMPLEMENTED** | No CSAT, sentiment, or survey logic. |

### Data & Analytics Domain
| CRM Capability | Status | Detailed Code Evidence |
|---|---|---|
| **CRM Analytics** | **NOT IMPLEMENTED** | Keywords route to `data_handler_node` ([`src/agents/orchestrator/handlers.py:94`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/orchestrator/handlers.py#L94)) which returns a static stub dictionary. No Data Agent exists. |
| **Report Generation** | **NOT IMPLEMENTED** | No SQL report generators or export renderers. |
| **Sales Analytics** | **NOT IMPLEMENTED** | No calculation engines for win rates, deal velocity, or quotas. |
| **Customer Analytics** | **NOT IMPLEMENTED** | No churn, LTV, or cohort analysis logic. |
| **Forecasting** | **NOT IMPLEMENTED** | No predictive models. |

### Non-CRM Infrastructure Present in Codebase
The following foundational systems **are fully implemented** and operational:
1. **Persistent Task Queue:** SQLite-backed asynchronous task queue with `PENDING`, `RUNNING`, `COMPLETED`, `FAILED` lifecycle, priority ordering, and payload storage ([`src/core/task.py`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/core/task.py)).
2. **Provider Infrastructure:** `BaseProvider` interface, `ProviderManager` registry, circuit breaker, exponential backoff, paid tier policy enforcement, `MockProvider`, and `OpenRouterProvider` with key redaction ([`src/providers/`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/providers/)).
3. **CLI Intake Layer:** Command-line intake via `argparse` with database registration and formatting ([`src/cli/`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/cli/)).
4. **LangGraph Execution Topologies:** Sequential graphs, conditional branching, loops with max iteration guards, parallel branches with `operator.add` fan-in ([`src/graph/`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/graph/)).

---

## PART 4 — Actual Task Execution Flow

Below is the exact execution trace of a task entering the system today, contrasting the **actual** code behavior against theoretical expectations:

```
[User / CLI Intake]
      │  (CLI: python -m src.main "Qualify lead John Doe")
      ▼
src/cli/intake.py: submit_task()
      │
      ├─► Step 1 [FUNCTIONAL]: Enqueues task into SQLite 'tasks' table with status='PENDING' (src/core/task.py: enqueue_task)
      ├─► Step 2 [FUNCTIONAL]: Updates SQLite task status to 'RUNNING' (src/core/task.py: update_task_status)
      │
      ▼
Grandparent Orchestrator (src/agents/orchestrator/orchestrator.py: GrandparentOrchestrator.aexecute())
      │
      ▼
Classifier Node (src/agents/orchestrator/classifier.py: create_classifier_node / classifier_node)
      │
      ├─► Step 3A [FUNCTIONAL]: classify_domain_confidence() runs deterministic keyword/prefix matching.
      │          │
      │          ├── If CONFIDENT (e.g. "sales_lead_scoring") ──► Returns domain ("sales"), classification_method="deterministic"
      │          │
      │          └── If UNCERTAIN (e.g. no keywords / ambiguous) ──► Invokes LLM Fallback (Step 3B)
      │
      ├─► Step 3B [FUNCTIONAL (Conditional)]: llm_classify_domain() queries ProviderManager -> OpenRouterProvider
      │          │  (Uses nvidia/nemotron-3.5-lightning:free via OpenRouter completions API)
      │          │
      │          ├── Valid domain returned ──► Returns domain, classification_method="llm"
      │          └── Error / Invalid output ──► Falls back to "unknown", classification_method="fallback"
      │
      ▼
LangGraph Conditional Router (src/agents/orchestrator/classifier.py: route_domain)
      │
      ├── Case A: Domain == "sales"
      │     ▼
      │   sales_handler_node (src/agents/orchestrator/handlers.py) [FUNCTIONAL DISPATCH]
      │     │
      │     ▼
      │   SalesDomainAgent.execute() (src/agents/sales/agent.py) [FUNCTIONAL DISPATCH]
      │     │
      │     ▼
      │   sales_classifier_node (src/agents/sales/classifier.py) [FUNCTIONAL DETERMINISTIC ROUTING]
      │     │  Classifies into subdomain: lead_management, opportunity_management, deal_management, general_sales
      │     │
      │     ▼
      │   Subdomain Handler (src/agents/sales/handlers.py) [STUB / PLACEHOLDER]
      │        Returns static dict: {"status": "COMPLETED", "details": "...processed successfully..."}
      │        (No database updates, no lead scoring, no external API calls)
      │
      ├── Case B: Domain == "marketing"
      │     ▼
      │   marketing_handler_node [STUB / PLACEHOLDER]
      │        Returns static dict: {"status": "DELEGATED", "details": "Task successfully delegated to Marketing Agent."}
      │
      ├── Case C: Domain == "customer_service"
      │     ▼
      │   customer_service_handler_node [STUB / PLACEHOLDER]
      │        Returns static dict: {"status": "DELEGATED", "details": "Task successfully delegated to Customer Service Agent."}
      │
      ├── Case D: Domain == "data"
      │     ▼
      │   data_handler_node [STUB / PLACEHOLDER]
      │        Returns static dict: {"status": "DELEGATED", "details": "Task successfully delegated to Data Agent."}
      │
      └── Case E: Domain == "unknown"
            ▼
          unknown_handler_node [STUB / PLACEHOLDER]
               Returns static dict: {"status": "UNRESOLVED", "details": "Task domain could not be identified..."}
      │
      ▼
Grandparent Orchestrator Final State (execution_status="SUCCESS", step=2)
      │
      ▼
src/cli/intake.py: submit_task()
      │
      ├─► Step 4 [FUNCTIONAL]: Updates SQLite 'tasks' table to status='COMPLETED' with result payload
      │
      ▼
[CLI Output / Terminal]
      Displays formatted execution result (JSON or text) to user.
```

### Critical Observation on TaskExecutor
In the architecture plan, tasks were intended to be picked up by worker loops via `TaskExecutor` (`src/core/task_executor.py`). Currently:
- The CLI (`src/cli/intake.py:63-83`) **bypasses `TaskExecutor`** and invokes `GrandparentOrchestrator.aexecute()` directly in-process after enqueuing.
- `TaskExecutor` remains an isolated utility from Milestone 3.3 wired to `create_task_graph` for foundation tests.
- Continuous background task picking and recovery are planned for Phase 6 (Milestone 6.1: Worker Loop & Recovery).

---

## PART 5 — LLM Integration and Agent Intelligence

Based on strict inspection of the codebase:

1. **Does the LLM only classify tasks, or can it execute business tasks too?**
   - **It only classifies tasks.** The LLM is used in exactly one place: `src/agents/orchestrator/classifier.py:275-303` (`llm_classify_domain`).
   - The LLM is prompted strictly to return a single token from `{"sales", "marketing", "customer_service", "data", "unknown"}`.
   - It cannot execute, generate, or modify any CRM data, draft messages, or perform actions.
2. **Does the Sales Agent have its own LLM connection?**
   - **No.** `SalesDomainAgent` (`src/agents/sales/agent.py`) is completely deterministic. It does not accept a `ProviderManager`, does not instantiate a provider, and does not make any LLM calls. Its subdomain classifier (`src/agents/sales/classifier.py`) uses regex and keyword sets only.
3. **Can a parent agent independently decide which child agent should receive a task?**
   - **Partially, via deterministic rule routing only.** The `SalesDomainAgent` (parent) routes tasks to one of four subdomains (`lead_management`, `opportunity_management`, etc.) via `classify_sales_task()`, which uses hardcoded keyword matching. It does not possess agentic reasoning or an LLM-assisted decision loop.
4. **Can child agents call tools or execute Python functions?**
   - **No child agents exist.** The endpoints are simple Python handler functions (`lead_management_handler`, etc.) that execute only string/dict formatting. They do not call database tools, external APIs, or other functions.
5. **How are results returned to the parent and Grandparent Orchestrator?**
   - **Via LangGraph State dictionaries.**
   - In `SalesDomainAgent`: each handler returns `{"execution_status": "SUCCESS", "handler_result": result_dict, "step": step + 1}` to `SalesAgentState`.
   - In `GrandparentOrchestrator`: `sales_handler_node` calls `sales_agent.execute(...)`, wraps that state in a `delegation_result["sales_agent_result"]` dict, and returns it to `OrchestratorState`.
   - The Orchestrator state is then persisted to the `tasks` SQLite table and displayed via CLI.
6. **Which parts are currently deterministic and which are genuinely agentic?**
   - **95% Deterministic / 5% LLM-Assisted Classification:**
     - Deterministic: CLI parsing, task enqueuing, primary domain classification, orchestrator conditional edges, sales agent instantiation, sales subdomain classification, subdomain handlers, marketing/support/data handlers, state aggregation, database updates.
     - LLM-Assisted: Only the fallback branch in the Orchestrator classifier when deterministic keywords produce zero hits or a tie.
     - **Genuinely Agentic:** Currently, no component exhibits full autonomous agency (multi-turn reasoning, dynamic tool selection, or iterative reflection). The system is a structured, graph-driven state router.

---

## PART 6 — Missing Components and Recommended Hierarchy

### A. Missing Parent / Domain Agents
1. **Marketing Domain Agent (`MarketingDomainAgent`):** Missing. Only `marketing_handler_node` exists as a stub.
2. **Customer Service Domain Agent (`CustomerServiceDomainAgent`):** Missing. Only `customer_service_handler_node` exists as a stub.
3. **Data Domain Agent (`DataDomainAgent`):** Missing. Only `data_handler_node` exists as a stub.

### B. Missing Specialist / Child Agents & Tools
1. **Under Sales:**
   - **Lead Management Specialist:** Missing. (Only `lead_management_handler` stub exists). Needs real lead intake, validation, scoring, and DB persistence.
   - **Opportunity Specialist:** Missing. (Only `opportunity_management_handler` stub exists).
   - **Deal & Quote Specialist:** Missing. (Only `deal_management_handler` stub exists).
2. **Under Marketing:**
   - **Campaign Specialist:** Missing.
   - **Email Drafter / Content Specialist:** Missing (Candidate for LLM reasoning).
3. **Under Customer Service:**
   - **Ticket Triage Specialist:** Missing.
   - **Customer Inquiry Resolver:** Missing.

### C. Missing CRM Core Functionality
- **Database Tables:** `leads`, `contacts`, `accounts`, `opportunities`, `deals`, `tickets`, `audit_logs` are completely absent from `metadata`. Only `tasks` exists.
- **CRUD Operations:** No CRM entity creation, retrieval, updating, or deleting functions exist.
- **Worker Polling Engine:** No background worker daemon exists to poll the task queue; tasks are executed synchronously within CLI invocation.

### D. What Existing Components are Placeholders?
- `src/agents/orchestrator/handlers.py: marketing_handler_node`
- `src/agents/orchestrator/handlers.py: customer_service_handler_node`
- `src/agents/orchestrator/handlers.py: data_handler_node`
- `src/agents/orchestrator/handlers.py: unknown_handler_node`
- `src/agents/sales/handlers.py: lead_management_handler`
- `src/agents/sales/handlers.py: opportunity_management_handler`
- `src/agents/sales/handlers.py: deal_management_handler`
- `src/agents/sales/handlers.py: general_sales_handler`

### E. Minimum Logical Hierarchy for a Functional Multi-Agent CRM
To avoid over-engineering and creating unnecessary agents for simple Python operations, the recommended minimal architecture follows this rule:
> **Rule:** Use **deterministic Python functions/tools** for data persistence, mathematical scoring, and schema transformations. Use **Agents** only where task decomposition, coordination, or LLM reasoning (e.g. classification, text drafting, unstructured comprehension) is required.

#### Minimum Logical Hierarchy:
1. **Grandparent Orchestrator (Orchestration Agent):**
   - Routes tasks across business domains using deterministic rules + LLM fallback.
2. **Sales Domain Agent (Domain Coordinator Agent):**
   - Coordinates sales subdomains.
   - Delegates to **Lead Specialist Agent** (for ambiguous leads requiring qualification/enrichment) or directly calls **Lead CRUD Tools** (for simple database operations).
3. **Lead Specialist Agent (Specialist Child Agent):**
   - Ingests lead data, runs scoring algorithms (deterministic tool), uses LLM for profile summarization or email drafting, and updates CRM state.
4. **CRM Tool Layer (Deterministic Functions, NOT Agents):**
   - `LeadStore` (SQLite CRUD operations)
   - `LeadScorer` (Heuristic scoring math)
   - `AuditLogger` (Database audit trail)

---

## PART 7 — Architecture Diagrams

### Diagram A: Current Implemented Architecture (Verified in Code)

```mermaid
flowchart TD
    CLI["CLI Intake Layer\n(src/cli/intake.py)"] -->|1. Enqueue Task| DB[(SQLite Tasks Table\nsrc/core/task.py)]
    CLI -->|2. aexecute()| Orch["Grandparent Orchestrator\n(src/agents/orchestrator/orchestrator.py)"]
    
    subgraph Orchestrator_Graph["Grandparent Orchestrator StateGraph"]
        Classifier["Classifier Node\n(classify_domain_confidence)"]
        LLMFallback["OpenRouter LLM Fallback\n(llm_classify_domain)"]
        
        Classifier -->|Confident| Router{"Conditional\nRouter"}
        Classifier -.->|Uncertain| LLMFallback
        LLMFallback --> Router
        
        Router -->|sales| H_Sales["sales_handler_node"]
        Router -->|marketing| H_Mkt["marketing_handler_node\n(STUB)"]
        Router -->|customer_service| H_CS["customer_service_handler_node\n(STUB)"]
        Router -->|data| H_Data["data_handler_node\n(STUB)"]
        Router -->|unknown| H_Unk["unknown_handler_node\n(STUB)"]
    end
    
    subgraph Sales_Domain_Graph["Sales Domain Agent StateGraph (Foundation)"]
        H_Sales -->|execute()| SalesAgent["SalesDomainAgent\n(src/agents/sales/agent.py)"]
        SalesAgent --> SalesClass["Sales Subdomain Classifier\n(classify_sales_task)"]
        SalesClass --> SalesRouter{"Sales\nRouter"}
        
        SalesRouter -->|lead_management| H_Lead["lead_management_handler\n(STUB)"]
        SalesRouter -->|opportunity_management| H_Opp["opportunity_management_handler\n(STUB)"]
        SalesRouter -->|deal_management| H_Deal["deal_management_handler\n(STUB)"]
        SalesRouter -->|general_sales| H_Gen["general_sales_handler\n(STUB)"]
    end
    
    subgraph External_Providers["Provider Abstraction Layer"]
        LLMFallback --> PM["ProviderManager\n(src/providers/manager.py)"]
        PM --> ORP["OpenRouterProvider\n(nvidia/nemotron-3.5-lightning:free)"]
    end
```

---

### Diagram B: Target Architecture (Complete Functional Multi-Agent CRM)

```mermaid
flowchart TD
    Intake["Intake Layer (CLI / FastAPI / Scheduler)"] --> Queue[(Task Queue - SQLite)]
    Worker["Background Worker Engine\n(Polling & Recovery)"] -->|Picks Task| Queue
    Worker --> Orch["Grandparent Orchestrator"]
    
    subgraph Top_Level["Grandparent Orchestrator"]
        OrchClassifier["Domain Classifier\n(Deterministic + LLM Fallback)"]
        OrchRouter{"Domain Router"}
        OrchClassifier --> OrchRouter
    end
    
    OrchRouter -->|Sales| SalesDomain["Sales Domain Agent"]
    OrchRouter -->|Marketing| MktDomain["Marketing Domain Agent\n[MISSING]"]
    OrchRouter -->|Service| CSDomain["Customer Service Domain Agent\n[MISSING]"]
    OrchRouter -->|Data| DataDomain["Data Domain Agent\n[MISSING]"]
    
    subgraph Sales_Domain["Sales Domain Hierarchy"]
        SalesDomain --> SalesRouter{"Sales Subdomain\nRouter"}
        SalesRouter --> LeadSpecialist["Lead Specialist Agent\n[MISSING]"]
        SalesRouter --> OppSpecialist["Opportunity Specialist Agent\n[MISSING]"]
        SalesRouter --> DealSpecialist["Deal Specialist Agent\n[MISSING]"]
    end
    
    subgraph Deterministic_Tools["CRM Tools & Data Layer (Pure Python & SQL)"]
        LeadSpecialist --> LeadTools["Lead CRUD & Validation Tools\n[MISSING]"]
        LeadSpecialist --> ScorerTool["Lead Scoring Engine\n[MISSING]"]
        LeadTools --> CRM_DB[(CRM Database:\nleads, contacts, accounts\n[MISSING])]
    end
    
    subgraph Intelligence_Routing["Task / Model Router (Cross-Cutting)"]
        SalesDomain -.-> Router["Model Router (Milestone 5.4)\n[PLANNED]"]
        LeadSpecialist -.-> Router
        Router --> LocalLLM["Ollama Local SLM\n(Milestone 5.3)"]
        Router --> CloudLLM["OpenRouter Cloud LLM\n(nvidia/nemotron)"]
    end
```

---

## PART 8 — Recommended Development Roadmap

The current roadmap remains intact. Below is the recommended implementation order for filling the architectural gaps without modifying completed milestones:

```
[COMPLETED MILESTONES]
├── Phase 1–3: Core Foundation, Persistence, Provider Abstraction, LangGraph Topologies ✅
├── Phase 4: Grandparent Orchestrator (4.1), Sales Agent Foundation (4.2), CLI Intake (4.3) ✅
├── Phase 5: OpenRouter Provider (5.1) ✅, LLM-Assisted Orchestrator Classification (5.2) ✅

[UPCOMING LOGICAL MILESTONE SEQUENCE]
│
├── Milestone 5.3 — Concrete Providers (Ollama & Groq)
│   • Build OllamaProvider for zero-cost local SLM inference.
│   • Build GroqProvider for high-speed cloud inference.
│   • Register both into ProviderManager.
│
├── Milestone 5.4 — Task / Model Router
│   • Implement capability levels (DETERMINISTIC, ML, LOCAL_SLM, CLOUD_LLM).
│   • Build router allowing domain agents to dynamically query the cheapest available provider.
│
├── Phase 6 — Reliability & Recovery
│   • Milestone 6.1: Async Worker Loop (decouples task queue polling from CLI execution).
│   • Milestone 6.2: Idempotency keys to prevent duplicate agent side effects.
│   • Milestone 6.3: Audit logging table for all agent decisions.
│
└── Phase 7 — First Real CRM Feature: Leads Domain
    • Milestone 7.1: SQLite `leads` schema and deterministic Lead CRUD tools.
    • Milestone 7.2: Replace `lead_management_handler` stub with real Lead Specialist Agent.
    • Milestone 7.3: Lead qualification & scoring engine (Deterministic heuristic math + LLM enrichment).
```

---

## Verification & Status Summary

- **Report Path:** `docs/AGENT_HIERARCHY_AUDIT.md`
- **Code Modifications:** None. All production code, test suites, and configurations remain untouched.
- **Git State:** Verified that only `docs/AGENT_HIERARCHY_AUDIT.md` has been created. Working tree remains clean and compliant with audit constraints.

