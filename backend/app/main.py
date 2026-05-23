from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langsmith.middleware import TracingMiddleware
from app.config import settings
from app.api.chat import router as chat_router
from app.api.auth import router as auth_router
from app.api.chats import router as chats_router
from app.api.scrape import router as scrape_router
from app.security import RateLimitMiddleware
from app.observability import RequestContextMiddleware
from contextlib import asynccontextmanager
import logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("Starting RankRoute Backend v2.0...")
    logging.info(f"Architecture: Policy-Driven Multi-Agent")
    logging.info(f"LLM Provider: {settings.llm_provider}")
    logging.info(f"Vector DB: {settings.vector_db}")
    
    from app.core.chroma_client import chroma_client
    logging.info(f"ChromaDB initialized at: {settings.chroma_persist_dir}")
    
    yield
    
    logging.info("Shutting down RankRoute Backend...")


app = FastAPI(
    title="RankRoute API",
    description="Policy-driven multi-agent admission counselor with deterministic rank prediction",
    version="2.0.0-alpha",
    lifespan=lifespan
)

allowed_origins = settings.cors_origins.split(",") if settings.cors_origins else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(TracingMiddleware)
app.add_middleware(RateLimitMiddleware, max_requests=settings.agent_rate_limit_per_minute)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )


app.include_router(chat_router)
app.include_router(auth_router)
app.include_router(chats_router)
app.include_router(scrape_router)


@app.get("/")
async def root():
    return {
        "message": "RankRoute API",
        "docs": "/docs",
        "health": "/api/health"
    }


@app.get("/api/health")
async def health_check():
    """Health check for load balancers and orchestrators."""
    try:
        from app.core.chroma_client import chroma_client
        chroma_client.client.heartbeat()
        chroma_ok = True
    except Exception:
        chroma_ok = False

    return {
        "status": "healthy" if chroma_ok else "degraded",
        "version": "2.0.0-alpha",
        "chroma": "ok" if chroma_ok else "unreachable",
    }
