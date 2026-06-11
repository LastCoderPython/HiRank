# Backend Setup

## Quick Start

### 1. Install Dependencies
```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your API keys:
#   GROQ_API_KEY      — LLM inference
#   SUPABASE_SERVICE_KEY — Auth + storage
#   TAVILY_API_KEY    — Live web search fallback
```

### 3. Ingest Web Content (one-shot)
```bash
# Ingest a single college
python scripts/ingest_web_content.py --college-code AEC

# Ingest all approved colleges
python scripts/ingest_web_content.py
```

### 4. Run Unit Tests
```bash
python -m pytest tests/ -v
```

### 5. Run the Server
```bash
uvicorn app.main:app --port 9000 --reload
```

Server starts at `http://localhost:9000`

### 6. Run End-to-End Test (server must be running)
```bash
python scripts/test_e2e.py
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Chat with streamed response |
| `/api/colleges` | GET | Get colleges by rank |
| `/api/health` | GET | Health check (ChromaDB, cache, policies) |
| `/api/scrape/run` | POST | Trigger ingestion for URLs |
| `/api/scrape/discover` | POST | Discover + ingest subpages for homepages |
| `/api/auth/phone/send-otp` | POST | Send email OTP |
| `/api/auth/phone/verify` | POST | Verify email OTP and create session |

## Utility Scripts

| Script | Purpose |
|--------|---------|
| `scripts/ingest_web_content.py` | One-shot web ingestion (no Celery needed) |
| `scripts/validate_existing_data.py` | Dry-run content validator against ChromaDB |
| `scripts/test_e2e.py` | End-to-end integration test |

## Project Structure
```
backend/
├── app/
│   ├── api/              # API routes
│   ├── core/             # Core RAG components
│   ├── ingestion/        # Web scraping, cleaning, validation
│   ├── models/           # Pydantic models
│   ├── orchestration/    # Multi-agent orchestrator
│   ├── services/         # Business logic
│   └── tasks/            # Celery tasks
├── data/                 # CSV data files + ChromaDB persist
├── scripts/              # Utility scripts
├── tests/                # Pytest unit tests
├── .env.example          # Environment variable template
├── docker-compose.yml    # Production deployment
└── Dockerfile            # Container image
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | Yes | — | LLM inference via Groq |
| `SUPABASE_SERVICE_KEY` | Yes | — | Supabase auth + DB |
| `TAVILY_API_KEY` | Yes | — | Live web search fallback |
| `REDIS_URL` | Docker | `redis://redis:6379/0` | Celery broker |
| `DEBUG` | No | `true` | Stack traces in errors |
| `FRONTEND_URL` | No | `http://localhost:3000` | CORS + OAuth redirect |
| `API_PORT` | No | `9000` | Backend listen port |
