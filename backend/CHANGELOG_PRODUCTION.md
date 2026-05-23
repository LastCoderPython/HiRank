# RankRoute Production Backend — Phase 1 Changelog

## Phase 1: Harden the Server ✅

### Changes Made

#### [MODIFY] `requirements.txt`
Added 6 production dependencies:
- `gunicorn` — Multi-worker process manager
- `trafilatura` — HTML content extraction (Phase 3)
- `tenacity` — Retry logic with exponential backoff
- `celery[redis]` — Distributed task queue (Phase 2)
- `redis` — Python Redis client
- `flower` — Celery monitoring dashboard

#### [MODIFY] `Dockerfile`
Replaced single-process `CMD ["python", "run.py"]` with production-grade setup:
- **Gunicorn + Uvicorn workers** (`-w 4`) for multi-core utilization
- **`--preload`** to load HuggingFace embedding model once before forking (prevents 4x RAM duplication)
- **Non-root `appuser`** for container security
- **System deps** (`libxml2-dev`, `libxslt1-dev`) for Trafilatura's lxml
- Proper timeouts (`--timeout 120`, `--graceful-timeout 30`)

#### [MODIFY] `app/main.py`
Added `/api/health` endpoint that checks ChromaDB connectivity. Returns `"healthy"` or `"degraded"` status for load balancer health checks.

#### [MODIFY] `app/config.py`
Added two new settings:
- `redis_url: str = "redis://localhost:6379/0"` — Celery broker connection
- `gunicorn_workers: int = 4` — Configurable worker count

---

## Phase 2: Separate API from Ingestion (Celery + Redis) ✅

### Changes Made

#### [NEW] `app/worker.py`
Celery app definition with:
- Redis as broker + result backend
- `task_acks_late=True` — if worker crashes, Redis re-queues the task automatically
- `worker_prefetch_multiplier=1` — prevents workers grabbing multiple heavy tasks
- Separate `ingestion` queue — chat API and ingestion never compete

#### [NEW] `app/tasks/__init__.py`
Package init for background tasks.

#### [NEW] `app/tasks/ingestion.py`
Ingestion pipeline as a Celery task:
- Same logic as original `scrape.py:_run_ingestion_job()` — zero behavior change
- Added `tenacity` retry wrapper for transient HTTP failures (429, 5xx)
- `autoretry_for=(Exception,)` with `max_retries=3` at task level
- Runs in Celery worker process, completely isolated from API

#### [MODIFY] `app/api/scrape.py`
Complete rewrite:
- **Removed:** `BackgroundTasks` parameter, `_jobs` in-memory dict, `_run_ingestion_job()` function
- **Added:** `run_ingestion_job.delay()` Celery dispatch
- **Added:** `AsyncResult` status lookup from Redis (durable across restarts)
- API contract (request/response models) unchanged — zero frontend breaking changes

#### [MODIFY] `docker-compose.yml`
Expanded from 1 service to 4:
- `api` — Gunicorn+Uvicorn FastAPI (serves user traffic)
- `worker` — Celery worker (processes ingestion jobs, `--concurrency=2`)
- `redis` — Message broker with AOF persistence and 256MB memory cap
- `flower` — Celery monitoring dashboard on `:5555`
- Both `api` and `worker` share `./data` volume for ChromaDB persistence

---

## Phase 3: Upgrade Cleaning Pipeline ✅

### Changes Made

#### [MODIFY] `app/ingestion/page_cleaner.py`
Replaced regex HTML parsing with Trafilatura:
- **`clean_html()`** now uses `trafilatura.extract()` as primary extractor with `include_tables=True` and `favor_recall=True`
- Original regex logic preserved as `_regex_fallback_clean()` for edge cases
- **`extract_title()`** now tries `trafilatura.extract_metadata()` first, falls back to regex
- **Public API unchanged:** `CleanedPage`, `clean_page()`, `classify_page_type()` — zero downstream impact
- `chunker.py`, `embedder.py`, `upsert_service.py` completely untouched

---

## Phase 4: Nginx, Scheduled Scraping ✅

### Changes Made

#### [NEW] `nginx/nginx.conf`
Nginx reverse proxy configuration:
- Rate limiting: 10 req/sec per IP, burst of 20, returns 429 on excess
- SSE support: `proxy_buffering off` for streaming chat responses
- Health check endpoint bypasses rate limiting
- `/docs` and `/redoc` blocked in production

#### [MODIFY] `app/worker.py`
Added Celery Beat schedule:
- Weekly full re-scrape every Monday at 3 AM
- Targets all approved college URLs
- Prevents knowledge base from going stale

#### [MODIFY] `docker-compose.yml`
Added 2 more services (total: 6):
- `nginx` — Reverse proxy on `:80`
- `beat` — Celery Beat scheduler (single replica)

#### [MODIFY] `.env.example`
Added `REDIS_URL`, `GUNICORN_WORKERS`, `DEBUG=false` for production

---

## Summary of All Changes

### New Files (4)
| File | Purpose |
|------|---------|
| `app/worker.py` | Celery app + Beat schedule |
| `app/tasks/__init__.py` | Task package |
| `app/tasks/ingestion.py` | Ingestion pipeline as Celery task |
| `nginx/nginx.conf` | Reverse proxy + rate limiting |

### Modified Files (7)
| File | Change |
|------|--------|
| `requirements.txt` | +6 production deps |
| `Dockerfile` | Gunicorn, non-root user, system deps |
| `docker-compose.yml` | 1 → 6 services |
| `app/config.py` | +redis_url, +gunicorn_workers |
| `app/main.py` | +/api/health endpoint |
| `app/ingestion/page_cleaner.py` | Trafilatura replaces regex |
| `app/api/scrape.py` | Celery replaces BackgroundTasks |
| `.env.example` | +Redis, Gunicorn, debug settings |

### Untouched Files (verified)
- All agent files (intent, prediction, web_knowledge, verifier)
- Orchestrator + policies
- `chunker.py`, `embedder.py`, `upsert_service.py`
- `scrape_runner.py`, `security.py`, `observability.py`
- ChromaDB layer

---

## Phase 5: Deep Observability (LangSmith) ✅

### Changes Made

#### [MODIFY] `.env.example`
Added LangSmith configuration variables (`LANGSMITH_TRACING`, `LANGSMITH_ENDPOINT`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`).

#### [MODIFY] `requirements.txt`
Added `langsmith` SDK to the RAG dependencies.

#### [MODIFY] `app/main.py`
Integrated `TracingMiddleware` into the FastAPI app to automatically group all backend processing traces under the parent HTTP request.

#### [MODIFY] Custom Function Tracing
Added `@traceable` decorators to non-LLM Python functions to visualize the full agentic logic flow in the LangSmith dashboard:
- `app/core/rag_pipeline.py`: `process_query` (run_type="chain")
- `app/services/query_parser.py`: `parse` (run_type="parser")
- `app/services/retriever.py`: `retrieve` (run_type="retriever")

---

## Phase 6: Self-Healing Zero-Trust RAG (Tavily Fallback) ✅

### Problem Solved
When ChromaDB had no answer for a student's question, the system would say "I don't know." Now it falls back to a live, domain-restricted web search and auto-heals its own knowledge gaps.

### Changes Made

#### [MODIFY] `requirements.txt`
Added `tavily-python` for live web search API.

#### [MODIFY] `app/config.py`
Added Tavily settings: `tavily_api_key`, `tavily_max_results`, `fallback_enabled`, `official_domain_suffixes`.

#### [MODIFY] `.env` and `.env.example`
Added `TAVILY_API_KEY` and `FALLBACK_ENABLED` variables.

#### [NEW] `app/services/domain_registry.py`
Single source of truth for trusted college domains:
- Maps college codes (AEC, JEC, NITS...) to their official domain variants
- Classifies any URL into 3 trust tiers: `official`, `educational`, `unofficial`
- Builds domain filter lists for Tavily queries
- Mirrors `scrape_runner.APPROVED_DOMAINS` in a structured format

#### [NEW] `app/services/web_search.py`
The core fallback engine with 5-step pipeline:
1. **Tavily Search** — domain-restricted query (official domains first)
2. **Zero-Trust Interceptor** — classifies every result URL by trust tier
3. **Grounding Pipeline** — unofficial sources must pass: consensus (2+ sources), date decay (<2yr), and minimum content length
4. **Context Builder** — merges results with trust badges (✅ OFFICIAL, ⚠️ COMMUNITY)
5. **Self-Healing Loop** — queues new official URLs into Celery for permanent ingestion

#### [MODIFY] `app/core/rag_pipeline.py`
Injected fallback at orchestrator level (NOT as an LLM tool):
- After `retriever.retrieve()` returns empty, Python code deterministically triggers `web_search_fallback.search()`
- Response includes `is_fallback`, `fallback_sources`, and `has_unofficial` metadata
- Wrapped in try/except — if Tavily is down, system degrades gracefully

#### [MODIFY] `app/tasks/ingestion.py`
Added `self_heal_ingest` Celery task:
- Accepts a single URL discovered by the Tavily fallback
- Runs the full pipeline: fetch → Trafilatura clean → chunk → embed → upsert
- Auto-derives college name from domain hostname
- `max_retries=2` with exponential backoff

---

## Phase 7: Codebase Audit, Legacy Cleanup, & Architecture Finalization
*(Completed)*

### Architecture Shift: Legacy RAG → Multi-Agent Orchestrator
- **[DELETE] `app/core/rag_pipeline.py` & `app/services/retriever.py` & `app/services/context_builder.py`**: Successfully removed the legacy RAG system. The old monolithic pipeline and hardcoded retriever logic (which included rank-forcing bugs) have been deleted.
- **[MODIFY] `app/api/chat.py`**: Fully decoupled streaming from the legacy RAG pipeline. Chat generation now routes exclusively via `supreme_orchestrator.py` and streams directly from `llm_client`.
- **[MODIFY] `app/orchestration/orchestrator.py`**: Replaced the flaky legacy fallback block with a graceful LLM instruction. If neither prediction nor web knowledge provides context, the LLM politely informs the user rather than hallucinating.

### 3-Tier Knowledge Retrieval System
- **[MODIFY] `app/orchestration/agents/web_knowledge_agent.py`**: Wired in the orphaned Live Web Search. The agent now operates on a strict 3-tier strategy:
  1. **Tier 1:** Local Vector Database (ChromaDB)
  2. **Tier 2:** Live Web Search Fallback (Tavily restricted domains via `app/services/web_search.py`)
  3. **Tier 3:** Structured Local Data Fallback (CSVs via `college_info_service.py`)
  - **[FIX] Fast-Fail Routing**: Fixed an early-return bug where an empty Vector Database would instantly skip Tier 2 (Live Search) and drop straight to Tier 3. It now correctly forwards the query to the Tavily API.
  - **[ENVIRONMENT]**: Installed `tavily-python` SDK to power the Live Web Search engine.

### Tech Debt Remediation & Future-Proofing
- **[DELETE] Legacy `app/agents/` Directory**: Purged the entire ghost folder containing obsolete architecture (`agents.py`, `retrieval.py`, `memory.py`, etc.) that were superseded by `app/orchestration/`.
- **[DELETE] Ghost API `app/api/agents.py`**: Removed the obsolete API endpoints (`/plan`, `/execute`) and unregistered the router from `app/main.py`.
- **[MODIFY] `app/orchestration/orchestrator.py`**: Fixed a critical crash bug by hardcoding `GREETING_RESPONSES` and `OFF_TOPIC_RESPONSES` instead of importing from the deleted RAG pipeline.
- **[MODIFY] Python 3.12 Readiness**: Replaced 18 deprecation usages of `datetime.utcnow()` with `datetime.now(timezone.utc)` across 6 critical files (`versioning_service.py`, `upsert_service.py`, `scrape_runner.py`, `supabase.py`, `education_schema.py`, `memory.py`).
- **[MODIFY] `data/college_info/fee_structure.csv`**: Fixed leading whitespace in column headers.
- **[MODIFY] `app/config.py`**: Added Pydantic `extra = "ignore"` to gracefully handle unmapped `.env` variables (such as LangSmith keys) and prevent startup crashes.

---

## Phase 8: Ingestion Registry Fixes & Validation ✅

### Changes Made

#### [MODIFY] `app/services/domain_registry.py`
- Fixed a broken ingestion URL for Jorhat Institute of Science & Technology (JIST). Replaced `https://www.jist.ac.in/` with `https://jist.ac.in/` due to upstream server misconfigurations (403 Forbidden on the `www` subdomain).
- Conducted deep diagnostic health checks on all 28 registered college domains to verify DNS, SSL, and network stability for the ingestion pipeline.

#### [NEW] `test_e2e.py`
- Added an End-to-End Orchestrator testing script to locally validate all Multi-Agent intents (Greeting, Prediction, Local Web Knowledge, Live Web Search).
- Ensured graceful degradation mechanisms (`[WinError 10061]` when Redis/Celery is offline) function correctly without crashing the RAG API.
