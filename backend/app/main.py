from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langsmith.middleware import TracingMiddleware
from app.config import settings
from app.api.chat import router as chat_router
from app.api.auth import router as auth_router
from app.api.chats import router as chats_router
from app.api.scrape import router as scrape_router
from app.api.profile import router as profile_router
from app.api.admin import router as admin_router
from app.api.colleges import router as colleges_router
from app.api.compare import router as compare_router
from app.api.analytics import router as analytics_router
from app.api.health import router as health_router
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.observability import RequestContextMiddleware
from app.middleware.csp import SecurityHeadersMiddleware
from contextlib import asynccontextmanager
import logging

# ── Server Readiness ──────────────────────────────────────────────────
server_state: str = "starting"  # starting → ready | degraded


@asynccontextmanager
async def lifespan(app: FastAPI):
    global server_state
    logging.info("Starting RankRoute Backend v2.0...")
    logging.info(f"Architecture: Policy-Driven Multi-Agent")
    logging.info(f"LLM Provider: {settings.llm_provider}")
    logging.info(f"Vector DB: {settings.vector_db}")

    # Phase 1: critical components (blocking — server won't serve until done)
    from app.core.llm_client import llm_client
    llm_client.ensure_initialized()
    logging.info("LLMClient initialized")

    from app.retrieval.cutoff_engine import cutoff_engine
    cutoff_engine._ensure_loaded()
    logging.info("CutoffEngine data loaded")

    from app.core.chroma_client import chroma_client
    chroma_client._ensure_initialized()
    logging.info("ChromaDB initialized at: %s", settings.chroma_persist_dir)

    # Phase 2: non-critical components (background thread, not needed for chat)
    def _init_embeddings():
        from app.core.embeddings import embedding_service
        embedding_service._ensure_initialized()
        logging.info("EmbeddingService initialized (background)")

    import threading
    bg_thread = threading.Thread(target=_init_embeddings, daemon=True)
    bg_thread.start()

    from app.services.log_service import log_service
    log_service.insert("system_event", "info", "Server started", {
        "llm_provider": settings.llm_provider,
        "vector_db": settings.vector_db,
    }, source="server.lifecycle")

    server_state = "ready"
    yield

    server_state = "starting"
    logging.info("Shutting down RankRoute Backend...")
    log_service.insert("system_event", "info", "Server shutting down", source="server.lifecycle")


app = FastAPI(
    title="RankRoute API",
    description="Policy-driven multi-agent admission counselor with deterministic rank prediction",
    version="2.0.0-alpha",
    lifespan=lifespan
)

allowed_origins = settings.cors_origins.split(",") if settings.cors_origins else []

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(TracingMiddleware)
app.add_middleware(RateLimitMiddleware, max_requests=settings.agent_rate_limit_per_minute)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.error(f"Unhandled exception: {exc}", exc_info=True)
    from app.services.log_service import log_service
    log_service.insert("error", "critical", f"Unhandled exception on {request.method} {request.url.path}", {
        "path": request.url.path,
        "method": request.method,
        "error": str(exc)[:500],
    }, source="server.exception")
    detail = str(exc) if settings.debug else "An unexpected error occurred. Please try again."
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": detail}
    )


app.include_router(chat_router)
app.include_router(auth_router)
app.include_router(chats_router)
app.include_router(scrape_router)
app.include_router(profile_router)
app.include_router(admin_router)
app.include_router(colleges_router)
app.include_router(compare_router)
app.include_router(analytics_router)
app.include_router(health_router)


@app.get("/")
async def root():
    return {
        "message": "RankRoute API",
        "docs": "/docs",
        "health": "/api/health"
    }

