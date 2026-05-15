from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models.requests import ChatRequest, CollegeFilterRequest
from app.models.responses import CollegeListResponse, CollegeInfo
from app.core.rag_pipeline import rag_pipeline
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
        
        processed = await rag_pipeline.process_query(message, history)
        
        if processed.get("is_off_topic"):
            yield f"data: {json.dumps({'type': 'token', 'data': processed['context']})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return
        
        if processed["colleges"]:
            yield f"data: {json.dumps({'type': 'colleges', 'data': processed['colleges']})}\n\n"
        
        stream = rag_pipeline.llm.generate_stream(
            context=processed["context"],
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
    try:
        colleges = rag_pipeline.get_colleges_by_rank(
            rank=rank,
            category=category,
            exam=exam,
            branch=branch,
            limit=limit
        )
        
        return CollegeListResponse(
            colleges=[CollegeInfo(**c) for c in colleges],
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
        
        return {
            "status": "healthy",
            "version": "1.0.0",
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
