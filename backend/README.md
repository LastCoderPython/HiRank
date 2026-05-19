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
 RequestFrame                   ├── WebKnowledgeAgent → Chroma / CSV fallback
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
    "freshness_bucket": "current",  # current, recent, historical
    "chunk_index": 0
}
```

### Local CSV Fallback

`data/college_info/` directory provides offline data for:
- `colleges_basic_info.csv` — name, location, established, affiliation
- `fee_structure.csv` — tuition, hostel, exam fees by category
- `placement_stats.csv` — branch-wise packages, placement rates
- `facilities.csv` — campus area, hostel capacity, amenities
- `seat_matrix.json` — branch-wise seat distribution
- `branch_details.json` — syllabus highlights, career scope
- `admission_process.json` — CEE/JEE counseling steps

---

## Project Structure

```
backend/
├── app/
│   ├── main.py                          # FastAPI app (v2.0.0-alpha)
│   ├── config.py                        # Settings & environment
│   ├── security.py                      # Rate limiting middleware
│   ├── observability.py                 # Request context middleware
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
│   │   ├── cutoff_engine.py             # 895-record CSV-backed engine
│   │   └── metadata_filters.py          # Chroma $and/$in filter builder
│   │
│   ├── ingestion/                       # ── Background Ingestion ──
│   │   ├── scrape_runner.py             # whitelisted-domain-only fetcher
│   │   ├── page_cleaner.py              # HTML cleaning + page classification
│   │   ├── chunker.py                   # section-aware semantic chunking
│   │   ├── embedder.py                  # batch HuggingFace embedding
│   │   └── upsert_service.py           # Chroma upsert with stable IDs
│   │
│   ├── api/
│   │   ├── chat.py                      # /api/chat, /api/colleges, /api/health
│   │   ├── scrape.py                    # /api/scrape/run, /api/scrape/status
│   │   ├── auth.py                      # authentication routes
│   │   ├── chats.py                     # chat history routes
│   │   └── agents.py                    # agent debug routes
│   │
│   ├── services/
│   │   ├── cache_service.py             # TTL cache (prediction, web, answer)
│   │   ├── versioning_service.py        # prompt/policy version tracking
│   │   ├── college_info_service.py      # local CSV college data
│   │   ├── context_builder.py           # legacy context assembly
│   │   ├── query_parser.py              # legacy query parsing
│   │   └── retriever.py                 # legacy vector retrieval
│   │
│   ├── core/
│   │   ├── rag_pipeline.py              # legacy RAG (fallback path)
│   │   ├── chroma_client.py             # ChromaDB interface
│   │   ├── embeddings.py                # embedding service
│   │   └── llm_client.py               # LLM interface (Groq)
│   │
│   ├── models/
│   │   ├── requests.py                  # Pydantic request models
│   │   └── responses.py                 # CollegeInfo, ChatStreamingResponse
│   │
│   └── utils/
│       └── helpers.py
│
├── data/
│   ├── cee_cutoffs.csv                  # CEE cutoff truth (575 records)
│   ├── jee_cutoffs.csv                  # JEE cutoff truth (320 records)
│   ├── college_info/                    # local CSV fallback data
│   └── chroma/                          # vector DB persistence
│
├── scripts/
│   ├── test_sprint3.py                  # engine + intent tests
│   ├── test_sprint5.py                  # module import + functional tests
│   ├── test_e2e.py                      # 6 live endpoint tests
│   ├── prepare_data.py                  # data ingestion script
│   └── ingest_data.py                   # legacy ingestion
│
├── requirements.txt
├── V2_MIGRATION_CHANGELOG.md            # detailed migration changelog
└── README.md                            # this file
```

---

## Approved Scraping Domains

Only whitelisted official domains are allowed for web ingestion:

| Category | Domains |
|----------|---------|
| **Colleges** | aec.ac.in, jecassam.ac.in, nits.ac.in, tezu.ernet.in, jist.ac.in, bbec.ac.in, bvec.ac.in, dec.ac.in, gecassam.ac.in |
| **University** | astu.ac.in |
| **Government** | dte.assam.gov.in, ceeassamonline.in, josaa.nic.in |

All domains include `www.` variants. Unapproved URLs return HTTP 400.

---

## Environment Variables

```env
# LLM Configuration
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key
PRIMARY_MODEL=llama-3.3-70b-versatile
FALLBACK_MODEL_1=llama-3.1-8b-instant
FALLBACK_MODEL_2=gemma2-9b-it

# Embedding Model
EMBEDDING_PROVIDER=huggingface
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Vector Database
VECTOR_DB=chroma
CHROMA_PERSIST_DIR=./data/chroma

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:3000

# Data Paths
CEE_DATA_PATH=./data/cee_cutoffs.csv
JEE_DATA_PATH=./data/jee_cutoffs.csv

# Feature Flags
ENABLE_AGENT_ROUTES=false
AGENT_RATE_LIMIT_PER_MINUTE=30
```

---

## Running Locally

```bash
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux/Mac

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment
copy .env.example .env
# Edit .env with your API keys

# 4. Start the server
uvicorn app.main:app --reload --port 8000

# 5. Run tests
python scripts/test_sprint5.py    # module + functional tests
python scripts/test_e2e.py        # live endpoint tests (server must be running)
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
