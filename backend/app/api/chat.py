from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models.requests import ChatRequest, CollegeFilterRequest
from app.models.responses import CollegeListResponse, CollegeInfo
from app.core.rag_pipeline import rag_pipeline
from app.orchestration.orchestrator import supreme_orchestrator
from app.retrieval.cutoff_engine import cutoff_engine
import json
import uuid
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    session_id = request.session_id or str(uuid.uuid4())
    
    history = None
    if request.history:
        history = [{"role": msg.role, "content": msg.content} for msg in request.history]
    
    return StreamingResponse(
        _generate_stream(request.message, history, session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Session-Id": session_id,
            "Access-Control-Allow-Origin": "*"
        }
    )


async def _generate_stream(message: str, history, session_id):
    try:
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
        
        # Route through the Supreme Orchestrator
        result = await supreme_orchestrator.handle_request(
            query=message,
            history=history,
            session_id=session_id,
        )
        
        response_type = result.get("response_type", "stream")
        
        # Direct responses (greetings, off-topic, clarifications)
        if response_type in ("direct", "clarification"):
            yield f"data: {json.dumps({'type': 'token', 'data': result['content']})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return
        
        # Send structured college data if available
        colleges = result.get("colleges", [])
        if colleges:
            yield f"data: {json.dumps({'type': 'colleges', 'data': colleges})}\n\n"
        
        # For prediction routes with cutoff evidence, stream via LLM
        prediction = result.get("prediction")
        content = result.get("content", "")
        processed = result.get("processed")
        
        if content:
            # Use the LLM to generate a natural language response
            # from the structured prediction context
            stream = rag_pipeline.llm.generate_stream(
                context=content,
                query=message,
                history=history
            )
            
            async for token in stream:
                if token:
                    yield f"data: {json.dumps({'type': 'token', 'data': token})}\n\n"
        
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        
    except Exception as e:
        logger.error(f"Streaming error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"


@router.get("/colleges")
async def get_colleges(
    rank: int,
    category: str = "General",
    branch: str = None,
    exam: str = "CEE",
    limit: int = 10
):
    """Deterministic college prediction using structured cutoff data.
    
    V2: Now uses the CutoffEngine (pandas-backed CSV data) instead of
    Chroma vector search. Results are auditable and reproducible.
    """
    try:
        colleges_raw = cutoff_engine.get_colleges_list(
            rank=rank,
            category=category,
            exam=exam,
            branch=branch,
            limit=limit,
        )
        
        colleges = []
        for c in colleges_raw:
            colleges.append(CollegeInfo(
                college_name=c["college_name"],
                college_code=c.get("college_code", ""),
                branch=c["branch"],
                category=c["category"],
                opening_rank=c.get("opening_rank", 0),
                closing_rank=c["closing_rank"],
                year=c["year"],
                match_percentage=c["match_percentage"],
                seat_type=c.get("seat_type", "Government"),
                band=c.get("band"),
            ))
        
        return CollegeListResponse(
            colleges=colleges,
            total=len(colleges),
            query_params={
                "rank": rank,
                "category": category,
                "branch": branch,
                "exam": exam,
                "limit": limit
            }
        )
    except Exception as e:
        logger.error(f"Error getting colleges: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    from app.core.chroma_client import chroma_client
    from app.config import settings
    
    try:
        cee_count = chroma_client.count_documents("cee")
        jee_count = chroma_client.count_documents("jee")
        engine_stats = cutoff_engine.get_stats()
        
        from app.services.cache_service import cache_service
        from app.services.versioning_service import versioning_service
        
        return {
            "status": "healthy",
            "version": "2.0.0-alpha",
            "architecture": "policy-driven-multi-agent",
            "models": {
                "provider": settings.llm_provider,
                "primary": settings.primary_model,
                "fallback_1": settings.fallback_model_1,
                "fallback_2": settings.fallback_model_2
            },
            "vector_db": {
                "type": settings.vector_db,
                "cee_documents": cee_count,
                "jee_documents": jee_count
            },
            "cutoff_engine": engine_stats,
            "cache": cache_service.get_stats(),
            "policy_versions": versioning_service.get_all_current(),
            "embedding": {
                "provider": settings.embedding_provider,
                "model": settings.embedding_model
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
