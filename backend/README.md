# RankRoute — Policy-Driven Multi-Agent Admission Counselor

> **Version:** 2.0.0-alpha  
> **Architecture:** Policy-driven, manager-controlled multi-agent system  
> **Stack:** FastAPI · Pandas · ChromaDB · Groq LLM · HuggingFace Embeddings

## Overview

RankRoute is an AI-powered admission counseling system for **Assam CEE** and **JEE Mains** students. It combines deterministic rank prediction from structured cutoff data with metadata-filtered web knowledge retrieval to deliver grounded, evidence-backed college recommendations.

### Key Design Principles

- **Deterministic first, LLM second** — structured CSV data handles rank predictions; LLM only synthesizes the final response.
- **Supreme Orchestrator owns the answer** — 4 specialist agents act as bounded tools, not autonomous responders.
- **Source authority enforced** — cutoff data is authoritative for ranks; web docs are authoritative for descriptions. Neither overrides the other.
- **Every response is verified** — the VerifierAgent checks evidence bundles before streaming.
- **Scraping is asynchronous** — web content enters via background ingestion jobs, never during live chat.

---

## Architecture

```
User Query
  │
  ▼
┌───────────────────────────────────────────────────┐
│             Supreme Orchestrator                   │
│  Parse → Route → Budget → Execute → Verify        │
└───┬─────────┬─────────┬─────────┬─────────┬───────┘
    │         │         │         │         │
    ▼         ▼         ▼         ▼         ▼
 Intent    Routing   Budget    Agents    Verifier
 Agent     Policy    Policy              Agent
    │                           │
    ▼                           ├── PredictionAgent → CutoffEngine (CSV)
 RequestFrame                   ├── WebKnowledgeAgent → Chroma → Tavily Fallback → CSV fallback
                                └── CacheService (TTL)
                                        │
                                        ▼
                                  LLM Synthesis → SSE Stream
```

### Request Lifecycle

1. **IntentAgent** — extracts rank, exam, category, branch, and intent type via regex (no LLM).
2. **RoutingPolicy** — classifies into 1 of 7 routes: `prediction_simple`, `descriptive_simple`, `mixed_comparison`, `recent_update`, `ambiguous`, `greeting`, `off_topic`.
3. **BudgetPolicy** — enforces per-tier call limits.
4. **Specialist Agents** — PredictionAgent (deterministic cutoff data) and/or WebKnowledgeAgent (Chroma + local CSV fallback) execute based on route.
5. **VerifierAgent** — validates evidence bundle: blocks rank claims without cutoff evidence, blocks source authority violations.
6. **Synthesis** — builds structured context from agent outputs, streams via LLM.

---

## API Endpoints

### POST /api/chat
Main chat endpoint with SSE streaming. Routes through the Supreme Orchestrator.

**Request:**
```json
{
  "message": "My rank is 3000 in CEE, which college can I get?",
  "session_id": "optional-session-id",
  "history": [
    {"role": "user", "content": "Previous message"},
    {"role": "assistant", "content": "Previous response"}
  ]
}
```

**Response:** SSE Stream
```
data: {"type": "session", "data": "session-id"}
data: {"type": "colleges", "data": [{...}, {...}]}
data: {"type": "token", "data": "Based"}
data: {"type": "token", "data": " on"}
...
data: {"type": "done"}
```

### GET /api/colleges
Deterministic college prediction using the CutoffEngine (no LLM involved).

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `rank` | int | required | User's rank |
| `category` | string | General | General/OBC/SC/ST |
| `branch` | string | null | Optional branch filter |
| `exam` | string | CEE | CEE or JEE |
| `limit` | int | 10 | Max results |

**Response:**
```json
{
  "colleges": [
    {
      "college_name": "Barak Valley Engineering College",
      "branch": "Mechanical",
      "closing_rank": 3250,
      "match_percentage": 93,
      "band": "safe",
      "category": "General",
      "year": 2024
    }
  ],
  "total": 5,
  "query_params": {"rank": 3000, "category": "General", "exam": "CEE"}
}
```

**Band classification:**
| Band | Condition | Match % |
|------|-----------|---------|
| safe | `user_rank ≤ closing_rank × 0.85` | 80-100% |
| target | `user_rank ≤ closing_rank × 1.10` | 60-75% |
| ambitious | `user_rank ≤ closing_rank × 1.40` | 35-55% |

### POST /api/scrape/run
Trigger a background scrape+ingestion job for approved URLs only.

**Request:**
```json
{
  "urls": ["https://www.aec.ac.in/placements"],
  "college_name": "AEC",
  "is_official": true
}
```

**Response:**
```json
{
  "job_id": "uuid",
  "status": "queued",
  "urls_queued": 1,
  "message": "Scrape job queued for 1 URL(s) under 'AEC'."
}
```

### GET /api/scrape/status/{job_id}
Check progress of a scrape+ingestion job.

**Response:**
```json
{
  "job_id": "uuid",
  "status": "completed",
  "urls_total": 1,
  "urls_completed": 1,
  "urls_failed": 0,
  "chunks_upserted": 12,
  "errors": [],
  "started_at": "2026-05-19T10:00:00",
  "completed_at": "2026-05-19T10:00:15"
}
```

### GET /api/health
System health with engine stats, cache metrics, and policy versions.

---

## Data Sources

### Cutoff Engine (Deterministic Truth)

| Exam | Records | Colleges | Years |
|------|---------|----------|-------|
| CEE | 575 | 7 | 2023, 2024 |
| JEE | 320 | 4 | 2023, 2024, 2025 |

**Source files:** `data/cee_cutoffs.csv`, `data/jee_cutoffs.csv`

### Chroma (Descriptive Web Knowledge)

Collection: `college_web_docs`

**Metadata per chunk:**
```python
{
    "college_name": "AEC",
    "page_type": "placement",      # placement, fees, hostel, about, admission, notice
    "source_url": "https://www.aec.ac.in/placements",
    "is_official": True,
    "domain": "aec.ac.in",
    "document_title": "AEC Placements 2024",
    "scraped_at": "2026-05-19T10:00:00",
    "content_hash": "a1b2c3d4e5f6",
    # (freshness computed dynamically at query time — not stored)
    "chunk_index": 0
}
```

### Tavily Live Web Search (Self-Healing Fallback)

If ChromaDB misses, the `web_search.py` engine performs a domain-restricted live search. 
- Results are tagged with trust badges (`[✅ OFFICIAL]`, `[⚠️ COMMUNITY]`)
- Unofficial URLs undergo strict consensus and date-decay grounding.
- Discovered official URLs are automatically pushed to the Celery `self_heal_ingest` task.

### Local CSV Fallback

`data/college_info/` directory provides offline data for:
- `colleges_basic_info.csv` — name, location, established, affiliation
- `fee_structure.csv` — tuition, hostel, exam fees by category
- `placement_stats.csv` — branch-wise packages, placement rates
- `facilities.csv` — campus area, hostel capacity, amenities
- `seat_matrix.csv` — branch-wise seat distribution
- `branch_details.json` — syllabus highlights, career scope
- `admission_process.json` — CEE/JEE counseling steps

---

## Project Structure

```
backend/
├── app/
│   ├── main.py                          # FastAPI app (v2.0.0-alpha)
│   ├── config.py                        # Settings & environment
│   ├── worker.py                        # Celery worker + beat schedule
│   │
│   ├── middleware/                       # ── Middleware Layer ──
│   │   ├── rate_limit.py                # Per-endpoint rate limiting
│   │   ├── observability.py             # Request context / logging
│   │   └── api_key_auth.py              # Agent API key auth
│   │
│   ├── orchestration/                   # ── Control Plane ──
│   │   ├── orchestrator.py              # Supreme Orchestrator (lifecycle)
│   │   ├── routing_policy.py            # 7 route categories
│   │   ├── source_policy.py             # cutoff_truth vs college_web_docs
│   │   ├── budget_policy.py             # per-tier call limits
│   │   ├── retrieval_policy.py          # metadata-first retrieval rules
│   │   ├── verification_policy.py       # pre-release evidence checks
│   │   ├── fallback_policy.py           # clarification / downgrade logic
│   │   ├── traces.py                    # per-request observability
│   │   ├── types.py                     # Pydantic contracts
│   │   └── agents/
│   │       ├── intent_agent.py          # rules-first intent extraction
│   │       ├── structured_prediction_agent.py  # deterministic cutoff prediction
│   │       ├── web_knowledge_agent.py   # Chroma + local CSV fallback
│   │       └── verifier_agent.py        # evidence bundle validation
│   │
│   ├── retrieval/                       # ── Deterministic Layer ──
│   │   ├── cutoff_engine.py             # CSV-backed prediction engine
│   │   └── metadata_filters.py          # Chroma $and/$in filter builder
│   │
│   ├── tasks/                           # ── Distributed Celery Workers ──
│   │   ├── __init__.py
│   │   ├── ingestion.py                 # async scraping/healing pipeline
│   │   └── enrichment.py                # passive profile enrichment
│   │
│   ├── ingestion/                       # ── ETL Logic ──
│   │   ├── scrape_runner.py             # whitelisted-domain-only fetcher
│   │   ├── page_cleaner.py              # Trafilatura HTML extraction
│   │   ├── chunker.py                   # section-aware semantic chunking
│   │   ├── content_validator.py         # page quality validation
│   │   ├── subpage_discovery.py         # homepage link discovery
│   │   ├── embedder.py                  # batch HuggingFace embedding
│   │   └── upsert_service.py            # Chroma upsert with stable IDs
│   │
│   ├── api/
│   │   ├── chat.py                      # POST /api/chat (SSE streaming)
│   │   ├── chats.py                     # CRUD /api/chats, /api/messages
│   │   ├── auth.py                      # authentication routes
│   │   ├── colleges.py                  # GET /api/colleges
│   │   ├── health.py                    # GET /api/health
│   │   ├── profile.py                   # GET/PATCH /api/profile
│   │   ├── scrape.py                    # POST /api/scrape/*
│   │   └── admin.py                     # Admin upload/validate/restore
│   │
│   ├── services/
│   │   ├── web_search.py                # Tavily live web fallback
│   │   ├── domain_registry.py           # Zero-trust allowlist
│   │   ├── data_ingestor.py             # CSV → ChromaDB ingestion
│   │   ├── cache_service.py             # TTL cache (prediction, web, answer)
│   │   ├── usage_service.py             # Freemium usage tracking (Redis)
│   │   ├── versioning_service.py        # prompt/policy version tracking
│   │   ├── alert_service.py             # Admin email alerts via SMTP
│   │   ├── college_info_service.py      # local CSV college data
│   │   ├── profile_enricher.py          # passive regex enrichment
│   │   └── email_validator.py           # disposable-domain blocklist
│   │
│   ├── core/
│   │   ├── chroma_client.py             # ChromaDB interface
│   │   ├── embeddings.py                # HuggingFace embedding service
│   │   └── llm_client.py               # LLM interface (Groq)
│   │
│   ├── db/
│   │   ├── supabase.py                  # Supabase client + queries
│   │   └── migrations/                  # SQL migration files
│   │       ├── V1__base_schema.sql
│   │       ├── V2__schema_fixes.sql
│   │       ├── V3__onboarding_fields.sql
│   │       └── V4__admin_role.sql
│   │
│   └── models/
│       ├── requests.py                  # Pydantic request models
│       └── responses.py                 # CollegeInfo, CollegeListResponse
│
├── data/
│   ├── cee_cutoffs.csv                  # CEE cutoff truth
│   ├── jee_cutoffs.csv                  # JEE cutoff truth
│   ├── college_info/                    # local CSV fallback data
│   ├── chroma/                          # vector DB persistence
│   ├── backups/                         # admin upload backups
│   └── archive/                         # legacy data archives
│
├── middleware/                           # migrated to app/middleware/
│
├── logs/                                # runtime log files
│   ├── server.log
│   └── error.log
│
├── scripts/
│   ├── ingest_data.py                  # CLI data ingestion
│   └── ingest_web_content.py           # one-shot web scrape
│
├── tests/                               # pytest test suite
│   ├── test_admin.py
│   ├── test_cutoff_engine.py
│   ├── test_domain_registry.py
│   └── test_validator.py
│
├── Caddyfile                            # Reverse proxy + rate limiting
├── Dockerfile                           # Production container
├── Dockerfile.caddy                     # Caddy container
├── docker-compose.yml                   # Multi-service orchestration
├── requirements.txt                     # Python dependencies
├── .env.example                         # Environment template
├── CHANGELOG_PRODUCTION.md              # detailed production changelog
└── README.md                            # this file
```

---

## Approved Scraping Domains

Managed strictly via `app/services/domain_registry.py`. Only whitelisted official domains are allowed for web ingestion and Tavily searches:

| Category | Domains |
|----------|---------|
| **Colleges** | aec.ac.in, jecassam.ac.in, nits.ac.in, tezu.ernet.in, jist.ac.in, bbec.ac.in, bvec.ac.in, dec.ac.in, gecassam.ac.in |
| **University** | astu.ac.in |
| **Government** | dte.assam.gov.in, ceeassamonline.in, josaa.nic.in |

*Note: The system automatically handles both root domains and `www.` variants for complete Zero-Trust authorization.*

---

## Environment Variables

```env
# Core API
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key
EMBEDDING_PROVIDER=huggingface
VECTOR_DB=chroma

# Fallbacks & Search
TAVILY_API_KEY=your_tavily_key
FALLBACK_ENABLED=true

# Distributed Workers
REDIS_URL=redis://redis:6379/0
GUNICORN_WORKERS=4

# Observability
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=your_langsmith_key
LANGSMITH_PROJECT=rankroute-v2
```

---

## Running in Production (Docker)

The absolute easiest way to run the full production stack (FastAPI, Redis, Celery Workers, Nginx, Flower):

```bash
# 1. Create environment file
cp .env.example .env
# Edit .env with your API keys (Groq, Tavily, LangSmith)

# 2. Start the entire cluster
docker-compose up -d --build
```

## Running Locally (Development)

```bash
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate          # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run FastAPI Server
uvicorn app.main:app --reload --port 8000

# 4. Run Celery Worker (requires local Redis running on 6379)
celery -A app.worker.celery_app worker --loglevel=info
```

---

## Testing

| Script | What it tests |
|--------|--------------|
| `scripts/test_sprint3.py` | CutoffEngine accuracy, IntentAgent parsing, PredictionAgent contracts |
| `scripts/test_sprint5.py` | All module imports, metadata filters, URL approval, page cleaning, chunking, verifier logic, orchestrator wiring |
| `scripts/test_e2e.py` | 6 live tests: health, colleges, prediction chat, descriptive chat, greeting, scrape rejection |

---

## Policies & Governance

| Policy | File | Purpose |
|--------|------|---------|
| Routing | `routing_policy.py` | Classifies queries into 7 route categories |
| Source Authority | `source_policy.py` | Defines which data source is authoritative for which query type |
| Budget | `budget_policy.py` | Limits LLM/agent calls per request tier |
| Retrieval | `retrieval_policy.py` | Enforces metadata-first Chroma queries |
| Verification | `verification_policy.py` | Blocks unsupported claims before streaming |
| Fallback | `fallback_policy.py` | Generates clarifying questions or downgrades when evidence is weak |

All policies are versioned and auditable via `versioning_service.py`.
