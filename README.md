# Agentic CRM

An extensible, hierarchical, agentic CRM system with cost-aware AI routing.

## Project Vision

Build a modular CRM that combines deterministic logic with intelligent agent orchestration, designed for:

- **Zero-cost operation** — uses only free-tier APIs and local models
- **Graceful degradation** — queues tasks when providers are unavailable
- **Incremental growth** — starts minimal, gains CRM capabilities over time
- **Event-driven architecture** — designed for eventual 24/7 operation

### Architecture Overview

```
Intake (CLI/API) → Grandparent Orchestrator → Domain Agents → Specialists/Tools
                                                    ↕
                                          Task/Model Router
                                                    ↕
                                    Provider Manager (local + cloud)
                                                    ↕
                                        SQLite Persistence
```

The system uses a **separate Task/Model Router** that selects the lowest-cost suitable execution method for each task:
1. Deterministic code (Python, SQL, rules)
2. Conventional ML/DL
3. Local small language model (via Ollama)
4. Free cloud LLM (Gemini, Groq, etc.)

**Paid APIs are never used automatically.** The system enforces a strict no-paid-fallback policy.

## Current Status

**Phase 1 — Project Foundation**

- [x] Milestone 1.1 — Project scaffold and configuration
- [x] Milestone 1.2 — Database foundation (async SQLite via SQLAlchemy Core + aiosqlite)
- [ ] Milestone 1.3 — Task model and queue

See [docs/roadmap.md](docs/roadmap.md) for the full phased plan and [docs/architecture.md](docs/architecture.md) for technical design.

## Quick Start

### Prerequisites

- Python 3.11 or later
- pip

### Setup

```bash
# Clone the repository
git clone https://github.com/<your-username>/agentic-crm.git
cd agentic-crm

# Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
# source .venv/bin/activate

# Install the project in editable mode with dev dependencies
pip install -e ".[dev]"

# Copy the environment template
cp .env.example .env
# Edit .env with your settings (all cloud API keys are optional)
```

### Run Tests

```bash
pytest
```

### Lint & Format

```bash
ruff check src/ tests/
ruff format src/ tests/
```

## Configuration

Configuration is loaded from environment variables (optionally via a `.env` file).

| Variable | Default | Description |
|---|---|---|
| `AGENTIC_CRM_LOG_LEVEL` | `INFO` | Logging level |
| `AGENTIC_CRM_ENV` | `development` | Environment name |
| `AGENTIC_CRM_DB_PATH` | `data/agentic_crm.db` | SQLite database file path (relative or absolute) |
| `AGENTIC_CRM_MAX_RETRIES` | `3` | Max retry attempts per provider |
| `AGENTIC_CRM_ALLOW_PAID_APIS` | `false` | Paid API policy (always false) |
| `GEMINI_API_KEY` | *(none)* | Google Gemini free-tier key |
| `GROQ_API_KEY` | *(none)* | Groq free-tier key |
| `OPENROUTER_API_KEY` | *(none)* | OpenRouter key (free models) |
| `HUGGINGFACE_API_KEY` | *(none)* | HuggingFace Inference API key |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama endpoint |
| `OLLAMA_DEFAULT_MODEL` | `phi3:mini` | Default local model |

**No API keys are required to start the application.** Missing keys simply disable the corresponding provider.

## Project Structure

```
agentic-crm/
├── docs/                  # Architecture and roadmap
├── src/                   # Application source code
│   ├── __init__.py
│   ├── config.py          # Configuration module
│   └── database/          # SQLite persistence (SQLAlchemy Core + aiosqlite)
│       ├── __init__.py
│       └── connection.py  # Async engine lifecycle and connection management
├── tests/                 # Test suite
│   ├── conftest.py
│   ├── test_config.py
│   └── test_database.py
├── .env.example           # Environment variable template
├── .gitignore
├── pyproject.toml
└── README.md
```

The database uses SQLite for local persistence, stored at `data/agentic_crm.db` by default. Override the location with `AGENTIC_CRM_DB_PATH`. Database files are excluded from Git via `.gitignore`.

## Security

- **Never commit `.env` files**, API keys, tokens, or private data.
- Use `.env.example` as a template — it contains only placeholders.
- All secrets are loaded from environment variables at runtime.
- Audit logging tracks all agent decisions (future milestone).

## License

MIT
