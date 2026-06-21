from fastapi import APIRouter, HTTPException, Cookie
from fastapi.responses import StreamingResponse
from app.models.requests import ChatRequest
from app.core.llm_client import llm_client
from app.orchestration.orchestrator import supreme_orchestrator
from app.api.auth import verify_jwt, fetch_user_from_supabase
import json
import uuid
import logging
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["chat"])


async def _get_user_from_cookie(sb_access_token: Optional[str]) -> Optional[dict]:
    """Extract user info from the access token cookie (non-throwing)."""
    if not sb_access_token:
        return None
    payload = verify_jwt(sb_access_token)
    if payload:
        return {
            "id": payload.get("sub"),
            "email": payload.get("email"),
        }
        
    user = await fetch_user_from_supabase(sb_access_token)
    if user:
        return {
            "id": user.get("id"),
            "email": user.get("email")
        }
        
    return None


@router.post("/chat")
async def chat_endpoint(
    request: ChatRequest,
    sb_access_token: Optional[str] = Cookie(None),
):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    session_id = request.session_id or str(uuid.uuid4())
    
    # Detect authenticated vs anonymous user
    user = await _get_user_from_cookie(sb_access_token)
    user_id = user["id"] if user else None

    # ── Anonymous Prompt Gate ─────────────────────────────────────
    if not user_id:
        try:
            from app.services.usage_service import usage_service
            credit_check = usage_service.check_and_increment_anon_prompt(session_id)
            if not credit_check.allowed:
                # Return auth_required SSE event immediately
                async def _auth_wall():
                    yield f"data: {json.dumps({'type': 'auth_required', 'reason': 'prompt_limit', 'used': credit_check.remaining + 3, 'limit': 3})}\n\n"
                return StreamingResponse(
                    _auth_wall(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Session-Id": session_id,
                    },
                )
        except Exception as e:
            logger.warning("Prompt gate check failed (fail-open): %s", e)

    history = None
    if request.history:
        history = [{"role": msg.role, "content": msg.content} for msg in request.history]
    
    return StreamingResponse(
        _generate_stream(request.message, history, session_id, user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Session-Id": session_id,
        }
    )


async def _generate_stream(message: str, history, session_id, user_id: Optional[str] = None):
    try:
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
        
        from app.services.cache_service import cache_service
        
        msg_lower = message.lower()
        
        # ── Phase 3: Journey State Machine ─────────────────────────────
        journey_state = cache_service.get("journey", session_id) or {
            "safe_colleges_identified": False,
            "documents_ready": False,
        }
        if "cutoff" in msg_lower or "predict" in msg_lower or "rank" in msg_lower:
            journey_state["safe_colleges_identified"] = True
        if "document" in msg_lower or "certificate" in msg_lower or "prc" in msg_lower:
            journey_state["documents_ready"] = True
        cache_service.set("journey", session_id, journey_state, ttl=86400)
        state_str = ", ".join([f"{k}: {'Yes' if v else 'No'}" for k,v in journey_state.items()])

        # ── Phase 3: Asynchronous Polling (Mock) ────────────────────────
        if "deep research" in msg_lower or "last 3 years" in msg_lower:
            yield f"data: {json.dumps({'type': 'token', 'data': 'This is a deep research question. I am analyzing the PDFs in the background. Please check back in a few minutes.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return
            
        # Short-Term Semantic Caching (Phase 2)
        cache_key = cache_service.make_key("query", msg_lower.strip())
        cached_response = cache_service.get("answer", cache_key)
        
        if cached_response:
            yield f"data: {json.dumps({'type': 'token', 'data': cached_response})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return
        
        # Route through the Supreme Orchestrator
        result = await supreme_orchestrator.handle_request(
            query=message,
            history=history,
            session_id=session_id,
            user_id=user_id,
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
        result.get("prediction")
        content = result.get("content", "")
        result.get("processed")
        
        if content:
            # Use the LLM to generate a natural language response
            # from the structured prediction context, using the constitutional
            # directive generated by the VerifierAgent for pre-flight behavioral guidance.
            constitutional_directive = result.get("constitutional_directive", "")
            stream = llm_client.generate_stream(
                context=content,
                query=message,
                history=history,
                state_str=state_str,
                constitutional_directive=constitutional_directive,
            )
            
            full_response = []
            async for token in stream:
                if token:
                    full_response.append(token)
                    yield f"data: {json.dumps({'type': 'token', 'data': token})}\n\n"
                    
            final_text = "".join(full_response)
            
            # Mechanical Guardrail & Caching
            if colleges:
                allowed_colleges = {c["college_name"].lower() for c in colleges}
                allowed_colleges.update({c["college_code"].lower() for c in colleges})
                
                from app.services.college_info_service import college_info_service
                import re
                
                # Dynamically build the list of ALL colleges in the database to catch hallucinations
                all_known_colleges = set()
                for code, info in college_info_service.colleges_info.items():
                    all_known_colleges.add(code.lower())
                    if info.get('name'):
                        all_known_colleges.add(info['name'].lower())
                
                unauthorized_mentioned = False
                for unauthorized in all_known_colleges:
                    if len(unauthorized) > 2: # Skip very short codes to avoid false positives
                        if re.search(r'\b' + re.escape(unauthorized) + r'\b', final_text.lower()) and not any(unauthorized in acc for acc in allowed_colleges):
                            unauthorized_mentioned = True
                            break
                
                if unauthorized_mentioned:
                    correction = "\n\n*(Guardrail Warning: The response above mentions a college that is not in your eligible safe/target list. Please rely only on the structured data.)*"
                    yield f"data: {json.dumps({'type': 'token', 'data': correction})}\n\n"
                    final_text += correction

            cache_service.set("answer", cache_key, final_text, ttl=900)
        
        # Build done event with optional tavily_skipped metadata
        done_payload = {"type": "done"}
        tavily_skipped = result.get("tavily_skipped", False)
        if tavily_skipped:
            try:
                from app.services.usage_service import usage_service
                done_payload["tavily_skipped"] = True
                done_payload["resets_on"] = usage_service.get_next_reset_date()
            except Exception:
                done_payload["tavily_skipped"] = True

        yield f"data: {json.dumps(done_payload)}\n\n"
        
        # Fire-and-forget passive profile enrichment
        if user_id:
            try:
                from app.tasks.enrichment import enrich_profile_from_message
                enrich_profile_from_message.delay(user_id, message)
            except Exception as e:
                logger.error("Failed to dispatch enrichment task: %s", e)
                pass # Never block the response
        
    except Exception as e:
        logger.error("Streaming error: %s", e)
        yield f"data: {json.dumps({'type': 'error', 'data': 'An error occurred while generating the response'})}\n\n"



