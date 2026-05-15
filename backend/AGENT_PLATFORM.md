# Autonomous Agent Platform

This backend now includes a modular multi-agent orchestration layer for education intelligence.

## Included Agent Modules

1. Autonomous data collection
2. PDF parsing
3. Social intelligence
4. Placement analysis
5. Dynamic updates
6. Search/research
7. Verification
8. Recommendation engine
9. Student memory
10. Hybrid RAG retrieval

## API Endpoints

- `GET /api/agents/catalog`
- `POST /api/agents/plan`
- `POST /api/agents/execute`
- `GET /api/agents/memory/{student_id}`
- `POST /api/agents/memory/{student_id}/note`
- `POST /api/agents/memory/{student_id}/preferences`

## Security and Observability

- API key auth for agent execution endpoints (`X-API-Key`)
- Rate limiting middleware for `/api/agents/*`
- Request tracing middleware (`x-request-id`, latency headers)

## RAG Architecture

- Hybrid semantic + keyword retrieval
- Metadata-aware reranking
- Chunk compression
- Source attribution and citation objects
- Verification confidence scoring

## Config

Add to `.env`:

```env
ENABLE_AGENT_ROUTES=true
AGENT_DEFAULT_COLLECTION=cee
AGENT_API_KEYS=local-dev-key
AGENT_RATE_LIMIT_PER_MINUTE=120
OBSERVABILITY_LOG_LEVEL=INFO
```

## Run

### Local

```bash
python run.py
```

### Docker

```bash
docker compose up --build
```

## Production Notes

- Replace in-memory memory store with Redis/Postgres-backed state.
- Wire social/search tools to trusted providers (SerpAPI, crawler jobs, queue workers).
- Run orchestrator workers with a queue (Celery/Arq/Kafka) for high concurrency.
- Export logs/metrics to OpenTelemetry + Prometheus + Grafana.
