# Agentic CRM — Complete CRM Agent Hierarchy Design

**Document Version:** 1.0.0  
**Milestone:** Phase 5, Milestone 5.3 — Complete CRM Agent Hierarchy Design  
**Date:** 2026-10-31  
**Target Hardware Profiles:** 8 GB & 16 GB RAM Consumer Laptops (CPU / Integrated GPU)  
**AI Strategy:** SLM-First (Small Language Models: 1B–3.8B), Local-First (Ollama/llama.cpp), Zero Cloud Mandate, Zero-Cost Ceiling ($0)

---

## 1. Executive Summary & Architectural Philosophy

The Agentic CRM is engineered as a modular, hierarchical, event-driven CRM combining deterministic software reliability with targeted Small Language Model (SLM) reasoning. It emulates the enterprise capability of enterprise platforms like Salesforce while adhering strictly to local hardware constraints (8 GB and 16 GB developer laptops).

### 1.1 Core Architectural Principles

1. **Agent Frugality & Pragmatism:**  
   An AI agent is **not** created for basic calculations, database queries, or CRUD operations. Deterministic Python functions and SQLAlchemy Core queries are used for all structured, repetitive, or mathematical tasks. Agents are deployed exclusively where natural language understanding, multi-turn reasoning, dynamic task decomposition, or unstructured data synthesis is genuinely required.

2. **SLM-First & Hardware Respect (8 GB / 16 GB RAM):**  
   Local deployment on 8 GB and 16 GB laptops cannot sustain monolithic 70B parameter models. The architecture prioritizes lightweight Small Language Models (e.g., Qwen2.5 1.5B/3B, Phi-3-mini 3.8B, Llama-3.2 1B/3B) that fit within 2 GB – 4 GB of RAM (quantized to 4-bit/Q4_K_M). Model lifecycle management (lazy loading and sequential execution) ensures that only one SLM is memory-resident during any single inference step.

3. **Strict Four-Level Hierarchy:**  
   The system defines clear boundaries:
   - **Level 1 (Top Level):** Grandparent Orchestrator (Intake, Domain Routing, Lifecycle Management).
   - **Level 2 (Domain Level):** 4 Domain Parent Agents (Sales, Marketing, Customer Service, Data & Analytics).
   - **Level 3 (Specialist Level):** 20 Dedicated Specialist Child Agents (5 per Domain).
   - **Level 4 (Operational Level):** Sub-Specialist Reasoning Units & Deterministic Python Toolkits.

4. **Status Definitions Used Across This Audit & Design:**
   - **`IMPLEMENTED`**: Production-tested code exists with verified test coverage.
   - **`PARTIALLY IMPLEMENTED`**: Foundation, state schema, or routing exists, but operational execution is incomplete.
   - **`PLACEHOLDER`**: Stub function or mock response registered in the graph returning static payloads.
   - **`PLANNED`**: Fully designed and specified in this document; slated for sequential future implementation.

---

## 2. Complete Four-Level CRM Hierarchy

```
LEVEL 1: GRANDPARENT ORCHESTRATOR [IMPLEMENTED]
 │
 ├── LEVEL 2: SALES DOMAIN AGENT [PARTIALLY IMPLEMENTED]
 │    ├── LEVEL 3: Lead Management Agent [PLANNED]
 │    │    ├── LEVEL 4 Sub-Specialist: Lead Qualification & Enrichment Agent [PLANNED]
 │    │    └── LEVEL 4 Tools: LeadStore (CRUD), DeduplicationEngine, RuleBasedScorer [PLANNED]
 │    ├── LEVEL 3: Contact Management Agent [PLANNED]
 │    │    └── LEVEL 4 Tools: ContactStore (CRUD), IdentityResolver, CommunicationLogger [PLANNED]
 │    ├── LEVEL 3: Account Management Agent [PLANNED]
 │    │    └── LEVEL 4 Tools: AccountStore (CRUD), HierarchyBuilder, HealthMetricCalculator [PLANNED]
 │    ├── LEVEL 3: Opportunity Management Agent [PLANNED]
 │    │    ├── LEVEL 4 Sub-Specialist: Opportunity Evaluation & Deal Strategy Agent [PLANNED]
 │    │    └── LEVEL 4 Tools: OpportunityStore (CRUD), StageTransitionValidator, PipelineCalculator [PLANNED]
 │    └── LEVEL 3: Deal Management Agent [PLANNED]
 │         ├── LEVEL 4 Sub-Specialist: Contract & Terms Reasoning Agent [PLANNED]
 │         └── LEVEL 4 Tools: DealStore (CRUD), DiscountCalculator, QuotePDFGenerator [PLANNED]
 │
 ├── LEVEL 2: MARKETING DOMAIN AGENT [PLANNED / STUB IN ORCHESTRATOR]
 │    ├── LEVEL 3: Campaign Management Agent [PLANNED]
 │    │    └── LEVEL 4 Tools: CampaignStore (CRUD), BudgetTracker, MultiChannelScheduler [PLANNED]
 │    ├── LEVEL 3: Email Marketing Agent [PLANNED]
 │    │    ├── LEVEL 4 Sub-Specialist: Email Copywriting & Personalization Agent [PLANNED]
 │    │    └── LEVEL 4 Tools: EmailTemplateRenderer, SMTPClient, BounceTracker [PLANNED]
 │    ├── LEVEL 3: Audience Segmentation Agent [PLANNED]
 │    │    ├── LEVEL 4 Sub-Specialist: Semantic Intent Segmenter [PLANNED]
 │    │    └── LEVEL 4 Tools: FilterRuleEvaluator, DynamicCohortGenerator, SQLSegmentExtractor [PLANNED]
 │    ├── LEVEL 3: Marketing Automation Agent [PLANNED]
 │    │    └── LEVEL 4 Tools: DripWorkflowEngine, EventTriggerWatcher, LeadHandoffBridge [PLANNED]
 │    └── LEVEL 3: Campaign Analytics Agent [PLANNED]
 │         └── LEVEL 4 Tools: ClickThroughCalculator, OpenRateAggregator, ROICalculator [PLANNED]
 │
 ├── LEVEL 2: CUSTOMER SERVICE DOMAIN AGENT [PLANNED / STUB IN ORCHESTRATOR]
 │    ├── LEVEL 3: Customer Support Agent [PLANNED]
 │    │    ├── LEVEL 4 Sub-Specialist: Inquiry Comprehension & Drafting Agent [PLANNED]
 │    │    └── LEVEL 4 Tools: KnowledgeBaseSearch, FAQRetriever, ConversationHistoryStore [PLANNED]
 │    ├── LEVEL 3: Ticket Management Agent [PLANNED]
 │    │    └── LEVEL 4 Tools: TicketStore (CRUD), SLAClockWatcher, PriorityQueueManager [PLANNED]
 │    ├── LEVEL 3: Ticket Classification Agent [PLANNED]
 │    │    ├── LEVEL 4 Sub-Specialist: Intent & Urgency Classifier [PLANNED]
 │    │    └── LEVEL 4 Tools: KeywordMatcher, RegexTriageRuleEngine [PLANNED]
 │    ├── LEVEL 3: Query Resolution Agent [PLANNED]
 │    │    ├── LEVEL 4 Sub-Specialist: Solution Synthesizer [PLANNED]
 │    │    └── LEVEL 4 Tools: OrderLookupTool, RefundTriggerTool, AccountVerificationTool [PLANNED]
 │    └── LEVEL 3: Customer Satisfaction Agent [PLANNED]
 │         ├── LEVEL 4 Sub-Specialist: Sentiment & Feedback Analysis Agent [PLANNED]
 │         └── LEVEL 4 Tools: CSATAggregator, SurveyDispatcher, ChurnRiskFlagEngine [PLANNED]
 │
 └── LEVEL 2: DATA & ANALYTICS DOMAIN AGENT [PLANNED / STUB IN ORCHESTRATOR]
      ├── LEVEL 3: Sales Analytics Agent [PLANNED]
      │    └── LEVEL 4 Tools: WinLossAggregator, VelocityCalculator, QuotaAttainmentTool [PLANNED]
      ├── LEVEL 3: Customer Analytics Agent [PLANNED]
      │    └── LEVEL 4 Tools: ChurnModelRunner, LTVCalculator, CohortRetentionTool [PLANNED]
      ├── LEVEL 3: Report Generation Agent [PLANNED]
      │    ├── LEVEL 4 Sub-Specialist: Executive Summary Generator [PLANNED]
      │    └── LEVEL 4 Tools: SQLQueryRunner, CSVExporter, MarkdownReportRenderer [PLANNED]
      ├── LEVEL 3: Sales Forecasting Agent [PLANNED]
      │    ├── LEVEL 4 Sub-Specialist: Qualitative Pipeline Review Agent [PLANNED]
      │    └── LEVEL 4 Tools: HistoricalTrendCalculator, WeightedProbabilityForecaster [PLANNED]
      └── LEVEL 3: Business Intelligence Agent [PLANNED]
           ├── LEVEL 4 Sub-Specialist: Anomaly & Strategic Insight Agent [PLANNED]
           └── LEVEL 4 Tools: KPIThresholdChecker, OutlierDetector, CrossDomainJoinEngine [PLANNED]
```

---

## 3. Deep-Dive: Roles & Responsibilities by Level

### Level 1 — Grandparent Orchestrator (`GrandparentOrchestrator`)
- **Status:** **`IMPLEMENTED`** ([`src/agents/orchestrator/orchestrator.py`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/orchestrator/orchestrator.py))
- **Role:** High-level coordinator and single point of entry for task decomposition and cross-domain dispatching.
- **Responsibilities:**
  1. Intake inbound tasks via CLI, API, or automated scheduler.
  2. Perform initial domain classification via two-tier routing:
     - *Tier 1 (Deterministic):* Fast keyword and exact pattern evaluation ([`classify_domain_confidence`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/orchestrator/classifier.py#L98)).
     - *Tier 2 (SLM Fallback):* Queries `ProviderManager` with structured prompt if Tier 1 is uncertain ([`llm_classify_domain`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/orchestrator/classifier.py#L275)).
  3. Dispatch task to the appropriate Level 2 Domain Agent StateGraph.
  4. Aggregate sub-graph results, update task queue state (`COMPLETED` / `FAILED`), and record execution metrics.
  5. Coordinate cross-domain workflows (e.g., Marketing -> Sales -> Support).

---

### Level 2 — Domain Parent Agents

#### A. Sales Domain Agent (`SalesDomainAgent`)
- **Status:** **`PARTIALLY IMPLEMENTED (FOUNDATION)`** ([`src/agents/sales/agent.py`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/sales/agent.py))
- **Responsibilities:**
  - Ingest all commercial revenue tasks.
  - Subdomain classification: routes tasks into Lead, Contact, Account, Opportunity, or Deal workflows.
  - Ensure commercial policy compliance (discount approval limits, pipeline stage consistency).
  - Aggregate specialist agent results into a cohesive sales transaction state.

#### B. Marketing Domain Agent (`MarketingDomainAgent`)
- **Status:** **`PLANNED`** (Orchestrator handler is currently a placeholder stub in [`src/agents/orchestrator/handlers.py:60`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/orchestrator/handlers.py#L60))
- **Responsibilities:**
  - Coordinate outbound campaigns, customer discovery, audience segmentation, and brand communication.
  - Oversee content generation, template rendering, and delivery schedule.
  - Track customer engagement signals and pass qualified prospects to the Sales Domain.

#### C. Customer Service Domain Agent (`CustomerServiceDomainAgent`)
- **Status:** **`PLANNED`** (Orchestrator handler is currently a placeholder stub in [`src/agents/orchestrator/handlers.py:77`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/orchestrator/handlers.py#L77))
- **Responsibilities:**
  - Ingest inbound customer tickets, support requests, bug reports, and inquiries.
  - Supervise ticket classification, priority assignment, SLA enforcement, and resolution synthesis.
  - Monitor customer satisfaction (CSAT) and escalate critical churn risks to Account Management.

#### D. Data & Analytics Domain Agent (`DataDomainAgent`)
- **Status:** **`PLANNED`** (Orchestrator handler is currently a placeholder stub in [`src/agents/orchestrator/handlers.py:94`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/orchestrator/handlers.py#L94))
- **Responsibilities:**
  - Maintain data hygiene, ETL import/export routines, and database deduplication.
  - Compute operational metrics (sales velocity, win rates, conversion funnels, churn rates).
  - Generate automated periodic reports and predictive revenue forecasts.

---

### Level 3 — Specialist Agents (20 Dedicated Units)

#### 1. Sales Domain Specialists

| Specialist Agent | Responsibility | Implementation Status | Intelligence Requirement |
|---|---|---|---|
| **Lead Management Agent** | Oversees lead lifecycle: ingestion, deduplication check, qualification rules, and handoff to opportunity. | **`PLANNED`** (currently `lead_management_handler` stub) | Hybrid: Deterministic deduplication + SLM qualification analysis. |
| **Contact Management Agent** | Maintains individual stakeholder records, interaction timelines, and contact hierarchy. | **`PLANNED`** | Deterministic tools for CRUD; SLM for unstructured contact enrichment. |
| **Account Management Agent** | Manages company/account entities, business health scores, multi-contact relationships, and parent-child enterprise accounts. | **`PLANNED`** | Deterministic database tools + Rule-based health metrics. |
| **Opportunity Management Agent** | Tracks active sales pipeline cycles, validates stage movement (e.g., Prospecting -> Discovery -> Proposal), and manages expected revenue dates. | **`PLANNED`** (currently `opportunity_management_handler` stub) | Deterministic state machine + SLM for deal blockage analysis. |
| **Deal Management Agent** | Governs pricing approvals, contractual terms, quote generation, and final closing activities. | **`PLANNED`** (currently `deal_management_handler` stub) | Hybrid: Deterministic price calculation + SLM contract clause review. |

#### 2. Marketing Domain Specialists

| Specialist Agent | Responsibility | Implementation Status | Intelligence Requirement |
|---|---|---|---|
| **Campaign Management Agent** | Plans, configures, schedules, and tracks multi-channel marketing campaigns and budgets. | **`PLANNED`** | Deterministic state machine & scheduling. |
| **Email Marketing Agent** | Manages newsletter drafting, subject-line optimization, message personalization, and delivery triggers. | **`PLANNED`** | SLM-heavy: Copywriting, subject line generation, tone adjustment. |
| **Audience Segmentation Agent** | Partitions contact database into dynamic cohorts based on behavioral rules, purchasing history, and firmographics. | **`PLANNED`** | Deterministic SQL filtering + SLM for natural-language segment queries. |
| **Marketing Automation Agent** | Manages multi-step drip logic, event-based workflow sequences, and sales handoff webhooks. | **`PLANNED`** | Deterministic state machine (LangGraph loop & conditional edges). |
| **Campaign Analytics Agent** | Computes campaign metrics: Open rates, Click-through rates (CTR), CAC, and attribution. | **`PLANNED`** | Deterministic Python & SQL math calculations. |

#### 3. Customer Service Domain Specialists

| Specialist Agent | Responsibility | Implementation Status | Intelligence Requirement |
|---|---|---|---|
| **Customer Support Agent** | Top-level intake for inbound customer communications; routes between self-service, FAQ, and ticketing. | **`PLANNED`** | SLM for conversational parsing and response drafting. |
| **Ticket Management Agent** | Manages ticket state lifecycle (New -> In Progress -> Escalated -> Resolved -> Closed), assignments, and SLA clocks. | **`PLANNED`** | Deterministic state transitions & SQLite operations. |
| **Ticket Classification Agent** | Analyzes customer text to identify ticket category (Billing, Technical, Account, Feature Request) and severity (Low, Medium, Urgent). | **`PLANNED`** | SLM classification fallback + keyword heuristic rules. |
| **Query Resolution Agent** | Synthesizes technical and commercial solutions by searching internal documentation and orders. | **`PLANNED`** | SLM retrieval comprehension & answer formulation. |
| **Customer Satisfaction Agent** | Evaluates post-interaction feedback, computes CSAT/NPS metrics, and flags high-risk accounts for intervention. | **`PLANNED`** | SLM sentiment evaluation + Deterministic score aggregation. |

#### 4. Data & Analytics Domain Specialists

| Specialist Agent | Responsibility | Implementation Status | Intelligence Requirement |
|---|---|---|---|
| **Sales Analytics Agent** | Calculates sales performance metrics: win/loss ratios, pipeline velocity, average contract value (ACV), rep performance. | **`PLANNED`** | Deterministic Python math + SQL aggregation. |
| **Customer Analytics Agent** | Computes retention rates, customer lifetime value (LTV), cohort analysis, and churn risk indices. | **`PLANNED`** | Deterministic statistical analysis + statistical ML. |
| **Report Generation Agent** | Converts raw analytical queries into structured Markdown, CSV, or formatted text reports with executive summaries. | **`PLANNED`** | Hybrid: Deterministic SQL queries + SLM executive summary writer. |
| **Sales Forecasting Agent** | Predicts quarter-close revenues based on weighted pipeline probabilities, historical seasonality, and rep commits. | **`PLANNED`** | Statistical time-series calculations + SLM qualitative commentary. |
| **Business Intelligence Agent** | Discovers strategic anomalies across sales, marketing, and support data to identify operational bottlenecks. | **`PLANNED`** | SLM pattern synthesis & anomaly interpretation. |

---

## 4. Level 4 — Sub-Specialist Agents vs. Deterministic Tools

An essential goal of this architecture is **avoiding agent bloat**. Sub-specialists are only instantiated as LLM/SLM reasoning units when autonomous interpretation is required. All other tasks are assigned to deterministic Python tools.

### 4.1 Detailed Breakdown for Key Specialists

#### Lead Management
- **LEVEL 4 Sub-Specialist Agent (Needs Reasoning):**
  - `Lead Qualification & Enrichment Agent`: Reads unstructured notes or website descriptions to determine B2B relevance, decision-maker seniority, and buyer intent.
- **LEVEL 4 Deterministic Tools (Zero AI, Pure Code):**
  - `LeadStore.create_lead(data)`: Validates schema and inserts record into `leads` table.
  - `LeadStore.update_lead(lead_id, data)`: Modifies lead records.
  - `DeduplicationEngine.find_duplicates(email, phone, company)`: Exact and fuzzy matching via SQLite query.
  - `RuleBasedScorer.calculate_score(lead_record)`: Computes base points for filled fields (e.g., corporate email: +15, phone present: +10, budget specified: +25).
  - `LeadAssignmentEngine.assign_to_rep(lead_id, territory)`: Deterministic round-robin or territory assignment.

#### Opportunity Management
- **LEVEL 4 Sub-Specialist Agent (Needs Reasoning):**
  - `Opportunity Strategy Agent`: Recommends negotiation tactics and next-best actions when a deal is stalled in "Evaluation" for over 14 days.
- **LEVEL 4 Deterministic Tools (Zero AI, Pure Code):**
  - `OpportunityStore.create_opportunity(account_id, amount)`: SQL insert.
  - `StageTransitionValidator.can_advance(opp_id, next_stage)`: Enforces business logic (e.g., cannot move to "Proposal" without an attached stakeholder contact).
  - `WeightedValueCalculator.compute(amount, probability)`: Pure math function ($100,000 \times 0.60 = \$60,000$).

#### Customer Service Ticket Classification
- **LEVEL 4 Sub-Specialist Agent (Needs Reasoning):**
  - `Sentiment & Intent Classifier`: Handles nuanced, emotional, or multi-topic customer complaints that fail regex rules.
- **LEVEL 4 Deterministic Tools (Zero AI, Pure Code):**
  - `RegexTriageEngine.match_keywords(text)`: Scans for "refund", "crash", "outage", "login failure" (matches >80% of routine cases instantly).
  - `SLAWatcher.calculate_time_to_breach(priority, created_at)`: Datetime subtraction against target SLA policy.

---

## 5. Agent-to-Agent Communication & Data Flow

Communication between agents is strictly mediated via **LangGraph State Dictionaries**. Agents do not open network sockets or make arbitrary direct method calls to one another.

### 5.1 Protocol Rules
1. **Vertical Flow (Orchestrator to Domain Agent):**  
   The Grandparent Orchestrator passes `OrchestratorState` down to the Domain Agent. The Domain Agent initializes its own typed state (e.g., `SalesAgentState`), executes its sub-graph, and returns its state dictionary back to the Orchestrator.
2. **Horizontal Flow (Cross-Domain Collaboration):**  
   Domain agents **never** communicate directly peer-to-peer. When a workflow crosses domains, it routes through the Grandparent Orchestrator:
   - *Example:* Marketing Campaign generates an inbound inquiry.
   - `MarketingDomainAgent` completes campaign intake -> returns task completion with handoff payload to Orchestrator.
   - `GrandparentOrchestrator` receives output -> generates child task `sales_lead_qualification` -> dispatches to `SalesDomainAgent`.
   - `SalesDomainAgent` completes qualification -> updates CRM database -> returns status to Orchestrator.

### 5.2 Flow Diagram: End-to-End Execution Pipeline

```
[ User Prompt / CLI / REST API ]
                │
                ▼
      src/core/task.py: enqueue_task()
                │  (Status: PENDING in SQLite 'tasks' table)
                ▼
      Grandparent Orchestrator (Level 1)
                │
                ├─► Deterministic Classifier (Keyword match)
                │         │  (Confident?)
                │         ├── YES ──► Route directly
                │         └── NO  ──► OpenRouter / Local SLM Fallback
                ▼
      Domain Parent Agent (Level 2) (e.g. SalesDomainAgent)
                │
                ├─► Subdomain Classifier (Deterministic rule router)
                ▼
      Specialist Child Agent (Level 3) (e.g. Lead Management)
                │
                ├─► Deterministic Tool Call (LeadStore: deduplication, schema check)
                │         │
                │         ▼
                ├─► Sub-Specialist Agent (Level 4) [If ambiguous qualification needed]
                │         │  (Local SLM inference: summarize intent, extract company size)
                │         ▼
                └─► Deterministic Tool Call (LeadStore: save lead; Scorer: compute score)
                │
                ▼
      [ Result Bubbles Up via LangGraph State: Specialist -> Parent -> Grandparent ]
                │
                ▼
      src/core/task.py: update_task_status(COMPLETED)
                │
                ▼
      [ CLI Output / Audit Log Entry / User Response ]
```

---

## 6. Shared Database & Tool Architecture

To ensure ACID reliability and zero-cost local execution, the system uses a centralized SQLite database managed by SQLAlchemy Core and `aiosqlite`.

### 6.1 Database Schema Plan (Target Tables)

```
┌────────────────────────────────────────────────────────────────────────┐
│                              SQLITE DATABASE                           │
├───────────────────────────────┬────────────────────────────────────────┤
│ SYSTEM / ORCHESTRATION TABLES │ CRM BUSINESS ENTITY TABLES             │
├───────────────────────────────┼────────────────────────────────────────┤
│ • tasks                       │ • leads                                │
│   (id, type, status, payload, │   (id, first_name, last_name, company, │
│    result, step, created_at)  │    email, phone, status, score, rep_id)│
│                               │ • contacts                             │
│ • task_queue                  │   (id, account_id, name, email, role)  │
│   (task_id, priority, worker) │ • accounts                             │
│                               │   (id, name, industry, tier, rev)      │
│ • idempotency_records         │ • opportunities                        │
│   (key, task_id, executed_at) │   (id, account_id, stage, amount, prob)│
│                               │ • deals                                │
│ • audit_logs                  │   (id, opp_id, terms, status, close_dt)│
│   (id, task_id, agent, action)│ • tickets                              │
│                               │   (id, contact_id, subject, priority)  │
│ • providers                   │ • campaigns                            │
│   (name, health, is_paid)     │   (id, title, budget, status, channel) │
└───────────────────────────────┴────────────────────────────────────────┘
```

### 6.2 Tool Service Layer Pattern
All database writes and mathematical operations are encapsulated in a pure Python `services/` or `tools/` layer:
```python
# Conceptual Tool Interface
class LeadTools:
    @staticmethod
    async def create_lead(db: DatabaseManager, lead_data: dict) -> str:
        """Deterministic SQL insert; returns new UUID."""
        ...
    @staticmethod
    async def score_lead(lead_data: dict) -> int:
        """Deterministic heuristic scoring algorithm."""
        ...
```
Agents call these tools as standard async methods. Database transactions remain outside the LangGraph nodes to preserve graph idempotency.

---

## 7. Hardware & Memory Optimization Strategy (8 GB & 16 GB Laptops)

The system is explicitly architected to operate efficiently on consumer hardware without dedicated GPUs:

### 7.1 Memory Allocation Budgets

| Target System | OS & Apps Budget | Agentic CRM Core (Python/SQLite) | Local SLM Budget (Quantized) | Headroom / Safety Buffer |
|---|---|---|---|---|
| **8 GB RAM Laptop** | 4.0 GB | 0.8 GB | **1.8 GB – 2.2 GB** (Qwen2.5-1.5B Q4 / Llama-3.2-1B) | 1.0 GB |
| **16 GB RAM Laptop**| 6.0 GB | 1.0 GB | **4.0 GB – 5.5 GB** (Qwen2.5-3B Q4 / Phi-3-mini 3.8B) | 3.5 GB |

### 7.2 SLM-First Operating Directives
1. **Model Parameter Cap:**  
   - 8 GB machines: Maximum parameter size **1.5 Billion** parameters (Q4 quantization).
   - 16 GB machines: Maximum parameter size **3.8 Billion** parameters (Q4 quantization).
2. **Lazy Model Lifecycle:**  
   The SLM is not permanently locked in system RAM. The model manager loads model weights into memory only during reasoning steps and automatically unloads or releases context buffers after a configurable idle cooldown (e.g., 60 seconds).
3. **Prompt Minimization:**  
   Prompts are structured with strict token constraints (typically under 200 input tokens and 50–100 completion tokens) to ensure rapid CPU inference times (<1.5 seconds per classification or extraction).
4. **Zero Forced Cloud Dependencies:**  
   All core features function completely offline via local SLM and deterministic tools. Cloud providers (such as OpenRouter free tier) serve purely as optional accelerations, never as mandatory operational dependencies.

---

## 8. Implementation Status Matrix

Every component across the CRM architecture is cataloged below with its current operational state:

| Component / Layer | Level | Status | Code Location |
|---|---|---|---|
| **Grandparent Orchestrator** | Level 1 | **`IMPLEMENTED`** | [`src/agents/orchestrator/orchestrator.py`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/orchestrator/orchestrator.py) |
| **Domain Classifier (Rule-based)** | Level 1 | **`IMPLEMENTED`** | [`src/agents/orchestrator/classifier.py:98`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/orchestrator/classifier.py#L98) |
| **Domain Classifier (SLM Fallback)**| Level 1 | **`IMPLEMENTED`** | [`src/agents/orchestrator/classifier.py:275`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/orchestrator/classifier.py#L275) |
| **ProviderManager & CircuitBreaker**| Infrastructure | **`IMPLEMENTED`** | [`src/providers/manager.py`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/providers/manager.py) |
| **OpenRouter Provider** | Infrastructure | **`IMPLEMENTED`** | [`src/providers/openrouter.py`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/providers/openrouter.py) |
| **Persistent Task Queue** | Infrastructure | **`IMPLEMENTED`** | [`src/core/task.py`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/core/task.py) |
| **CLI Intake Interface** | Intake | **`IMPLEMENTED`** | [`src/cli/intake.py`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/cli/intake.py) |
| **Sales Domain Agent** | Level 2 | **`PARTIALLY IMPLEMENTED`** | [`src/agents/sales/agent.py`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/sales/agent.py) |
| **Sales Subdomain Classifier** | Level 2 | **`IMPLEMENTED`** | [`src/agents/sales/classifier.py`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/sales/classifier.py) |
| **Sales Subdomain Handlers** | Level 3 | **`PLACEHOLDER`** | [`src/agents/sales/handlers.py`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/sales/handlers.py) |
| **Marketing Domain Agent** | Level 2 | **`PLACEHOLDER`** (Stub in Orchestrator) | [`src/agents/orchestrator/handlers.py:60`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/orchestrator/handlers.py#L60) |
| **Customer Service Domain Agent** | Level 2 | **`PLACEHOLDER`** (Stub in Orchestrator) | [`src/agents/orchestrator/handlers.py:77`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/orchestrator/handlers.py#L77) |
| **Data & Analytics Domain Agent** | Level 2 | **`PLACEHOLDER`** (Stub in Orchestrator) | [`src/agents/orchestrator/handlers.py:94`](file:///c:/Users/user/OneDrive/Desktop/Agentic%20CRM/src/agents/orchestrator/handlers.py#L94) |
| **All 20 Specialist Child Agents** | Level 3 | **`PLANNED`** | Specified in Section 3 of this document |
| **All Operational Level 4 Tools** | Level 4 | **`PLANNED`** | Specified in Section 4 of this document |
| **CRM Entity Schemas (Leads, etc.)**| Database | **`PLANNED`** | Specified in Section 6 of this document |
| **Async Background Worker Loop** | Infrastructure | **`PLANNED`** | Scheduled for Phase 6 |
| **Model Router & Fallback Chain** | Infrastructure | **`PLANNED`** | Scheduled for Milestone 5.5 |

---

## 9. Recommended Post-5.3 Development Sequence

To build out the complete hierarchy cleanly without creating architectural debt, the following milestone progression is recommended:

```
[CURRENT] Milestone 5.3: Complete CRM Agent Hierarchy Design (Complete ✅)
   │
   ▼
Milestone 5.4 — Local SLM Provider (Ollama / llama.cpp)
   • Implement OllamaProvider adhering to BaseProvider interface.
   • Verify local inference with lightweight SLM (Qwen2.5-1.5B or Phi-3-mini) within 2GB RAM budget.
   • Ensure zero mandatory cloud API connectivity.
   │
   ▼
Milestone 5.5 — Task / Model Router
   • Implement capability levels (DETERMINISTIC, LOCAL_SLM, CLOUD_LLM).
   • Route tasks to deterministic code first, then local SLM, falling back to cloud LLM only if configured.
   │
   ▼
Phase 6 — Reliability & Background Processing
   • Milestone 6.1: Async Worker Loop (background polling of SQLite task queue).
   • Milestone 6.2: Idempotency keys to guarantee duplicate prevention.
   • Milestone 6.3: Database audit logging for agent actions.
   │
   ▼
Phase 7 — Real CRM Entities & First Functional Specialist: Leads Domain
   • Milestone 7.1: SQLite `leads` table and deterministic CRUD tools (`LeadStore`).
   • Milestone 7.2: Real `LeadManagementAgent` (replacing placeholder handler in SalesDomainAgent).
   • Milestone 7.3: Heuristic scoring engine + SLM qualification enrichment.
   │
   ▼
Phase 8 — Expanding Remaining Sales Specialists (Opportunities, Deals, Accounts)
   • Wire real database schemas and domain agents into the Sales hierarchy.
   │
   ▼
Phase 9 — Customer Service & Marketing Domain Agent Buildout
   • Implement `CustomerServiceDomainAgent` with Ticket Management.
   • Implement `MarketingDomainAgent` with Campaign & Email drafting.
```

---

## 10. Summary Confirmation

This document completes the structural and functional design specification for the entire Agentic CRM. It establishes clear boundaries between reasoning agents and deterministic tools, respects local laptop hardware budgets, preserves the existing codebase and completed milestones, and provides a dependable blueprint for all subsequent development phases.

