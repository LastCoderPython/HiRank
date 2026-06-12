"""
RankRoute V2 — Supreme Orchestrator

The single manager component responsible for composing the final answer.
It receives the request context, applies the policy layer, dispatches
specialist agents, collects structured outputs, invokes the verifier,
and streams one final grounded response.

Responsibilities:
  - Own the final answer.
  - Never compute admission truth by itself.
  - Never bypass source authority rules.
  - Enforce request budgets and agent activation limits.
  - Trigger clarifying questions or fallback when evidence is weak.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from app.orchestration.routing_policy import routing_policy, RouteCategory
from app.orchestration.budget_policy import budget_policy
from app.orchestration.verification_policy import VerificationVerdict
from app.orchestration.fallback_policy import fallback_policy
from app.orchestration.traces import RequestTrace
from app.orchestration.types import (
    RequestFrame,
    PredictionAgentOutput,
    WebKnowledgeOutput,
    VerifierOutput,
)

logger = logging.getLogger("rankroute.orchestrator")


class SupremeOrchestrator:
    """
    Manager-controlled orchestrator that uses specialist agents as tools.
    
    Flow:
      1. Parse → build RequestFrame
      2. Route → determine which agents to call
      3. Budget → enforce cost limits
      4. Execute → call specialist agents
      5. Verify → check evidence bundle
      6. Respond → stream final answer
    """

    def __init__(self):
        from app.orchestration.agents.intent_agent import intent_agent
        from app.orchestration.agents.structured_prediction_agent import structured_prediction_agent
        from app.orchestration.agents.web_knowledge_agent import web_knowledge_agent
        from app.orchestration.agents.verifier_agent import verifier_agent
        from app.services.cache_service import cache_service

        self._intent_agent = intent_agent
        self._prediction_agent = structured_prediction_agent
        self._web_knowledge_agent = web_knowledge_agent
        self._verifier_agent = verifier_agent
        self._cache = cache_service

    # ── Public API ────────────────────────────────────────────────────

    async def handle_request(
        self,
        query: str,
        history: Optional[List[Dict[str, str]]] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Primary entry point. Returns a dict with:
          - "response_type": "stream" | "clarification" | "direct"
          - "content": the final text or clarification question
          - "colleges": optional structured college list
          - "trace": request trace dict for observability
        """
        trace = RequestTrace()

        # ── Step 1: Build RequestFrame ──────────────────────────────
        trace.start_stage("intent_parsing")
        frame = await self._parse_intent(query)
        # Attach user/session context for downstream credit enforcement
        frame.user_id = user_id
        frame.session_id = session_id
        trace.detected_intent = frame.intent
        trace.end_stage()

        # ── Step 2: Route ───────────────────────────────────────────
        trace.start_stage("routing")
        route = routing_policy.resolve(frame)
        trace.selected_route = route.value
        trace.end_stage()

        # ── Step 3: Budget ──────────────────────────────────────────
        budget = budget_policy.get_budget(route)
        specialist_calls_made = 0

        # ── Step 4: Execute agents based on route ──────────────────
        prediction_output: Optional[PredictionAgentOutput] = None
        web_output: Optional[WebKnowledgeOutput] = None

        if route == RouteCategory.GREETING:
            trace.log()
            return self._build_greeting_response(trace)

        if route == RouteCategory.OFF_TOPIC:
            trace.log()
            return self._build_off_topic_response(trace)

        if route == RouteCategory.AMBIGUOUS:
            fallback = fallback_policy.decide(
                missing_fields=self._detect_missing_fields(frame),
                intent=frame.intent,
            )
            trace.fallback_reason = fallback.reason or fallback.clarification_question
            trace.log()
            return {
                "response_type": "clarification",
                "content": fallback.clarification_question or "Could you provide more details?",
                "colleges": [],
                "trace": trace.to_dict(),
            }

        if route in (RouteCategory.PREDICTION_SIMPLE, RouteCategory.MIXED_COMPARISON):
            if specialist_calls_made < budget.max_specialist_calls:
                trace.start_stage("structured_prediction")
                trace.record_agent("structured_prediction_agent")

                # Check prediction cache first
                cache_key = self._cache.make_key(
                    frame.rank, frame.category, frame.exam, frame.branch_preference
                )
                cached = self._cache.get("prediction", cache_key)
                if cached is not None:
                    prediction_output = cached
                    trace.retrieval_sources.append("cache:prediction")
                    logger.info("Cache HIT for prediction key=%s", cache_key[:12])
                else:
                    try:
                        prediction_output = await asyncio.wait_for(
                            self._run_prediction(frame), timeout=20.0
                        )
                    except asyncio.TimeoutError:
                        logger.error("Prediction agent timed out after 20s")
                        prediction_output = None
                    if prediction_output is not None:
                        self._cache.set("prediction", cache_key, prediction_output)
                    specialist_calls_made += 1
                trace.end_stage()

        if route in (RouteCategory.DESCRIPTIVE_SIMPLE, RouteCategory.MIXED_COMPARISON, RouteCategory.RECENT_UPDATE):
            if specialist_calls_made < budget.max_specialist_calls:
                trace.start_stage("web_knowledge")
                trace.record_agent("web_knowledge_agent")
                try:
                    web_output = await asyncio.wait_for(
                        self._run_web_knowledge(frame), timeout=20.0
                    )
                except asyncio.TimeoutError:
                    logger.error("Web knowledge agent timed out after 20s")
                    web_output = None
                specialist_calls_made += 1
                trace.end_stage()
            else:
                logger.info("Budget exhausted: skipping web_knowledge_agent (used %d/%d)",
                           specialist_calls_made, budget.max_specialist_calls)

        # ── Step 5: Verify via VerifierAgent ──────────────────────
        trace.start_stage("verification")
        trace.record_agent("verifier_agent")
        try:
            verifier_output = await asyncio.wait_for(
                self._verifier_agent.run(
                    frame=frame,
                    prediction=prediction_output,
                    web_knowledge=web_output,
                ), timeout=20.0
            )
        except asyncio.TimeoutError:
            logger.error("Verifier agent timed out after 20s")
            # Synthesize a permissive verifier output so the flow continues
            verifier_output = VerifierOutput(
                approved=True,
                issues=["verifier_timeout"],
                missing_fields=[],
            )
        trace.verifier_flags = verifier_output.issues
        trace.end_stage()

        # Map verifier output to policy verdicts for flow control
        if verifier_output.missing_fields:
            verification_verdict = VerificationVerdict.CLARIFICATION_REQUIRED
        elif not verifier_output.approved and "source_authority_violated" in verifier_output.issues:
            verification_verdict = VerificationVerdict.BLOCKED
        elif not verifier_output.approved and "rank_claim_without_cutoff_evidence" in verifier_output.issues:
            verification_verdict = VerificationVerdict.BLOCKED
        elif not verifier_output.approved:
            verification_verdict = VerificationVerdict.DOWNGRADED
        else:
            verification_verdict = VerificationVerdict.APPROVED

        if verification_verdict == VerificationVerdict.CLARIFICATION_REQUIRED:
            fallback = fallback_policy.decide(missing_fields=verifier_output.missing_fields)
            trace.fallback_reason = fallback.clarification_question
            trace.log()
            return {
                "response_type": "clarification",
                "content": fallback.clarification_question or "I need more information to help you.",
                "colleges": [],
                "trace": trace.to_dict(),
            }

        if verification_verdict == VerificationVerdict.BLOCKED:
            trace.fallback_reason = verifier_output.downgrade_reason
            trace.log()
            return {
                "response_type": "direct",
                "content": verifier_output.downgrade_reason or "I cannot provide a confident answer with the available data.",
                "colleges": [],
                "trace": trace.to_dict(),
            }

        # ── Step 6: Build final response ────────────────────────────
        trace.start_stage("synthesis")
        result = await self._synthesize(frame, prediction_output, web_output, history)
        trace.end_stage()

        trace.log()
        result["trace"] = trace.to_dict()
        return result

    # ── Private helpers ────────────────────────────────────────────────

    async def _parse_intent(self, query: str) -> RequestFrame:
        """Parse the raw query into a structured RequestFrame
        using the IntentAgent (rules-first approach)."""
        output = await self._intent_agent.run(query)
        return self._intent_agent.to_request_frame(output, raw_query=query)

    async def _run_prediction(self, frame: RequestFrame) -> PredictionAgentOutput:
        """Run the structured prediction agent (deterministic, cutoff-backed)."""
        return await self._prediction_agent.run(frame)

    async def _run_web_knowledge(self, frame: RequestFrame) -> WebKnowledgeOutput:
        """Run the web knowledge agent (metadata-filtered Chroma + local fallback)."""
        return await self._web_knowledge_agent.run(frame)

    async def _synthesize(
        self,
        frame: RequestFrame,
        prediction: Optional[PredictionAgentOutput],
        web_knowledge: Optional[WebKnowledgeOutput],
        history: Optional[List[Dict[str, str]]],
    ) -> Dict[str, Any]:
        """Synthesize the final answer from agent outputs.

        Builds structured context from:
          - Prediction output (cutoff engine evidence)
          - Web knowledge output (Chroma chunks + local fallback)
        Then either returns context for LLM streaming or falls through
        to the legacy RAG pipeline if neither agent produced output.
        """
        colleges_for_display = []
        context_parts = []

        # ── Build context from prediction output ───────────────────
        if prediction and prediction.evidence_rows_used > 0:
            context_parts.append("=== ADMISSION PREDICTION (STRUCTURED CUTOFF DATA) ===")
            context_parts.append(f"User Rank: {frame.rank} | Category: {frame.category} | Exam: {frame.exam or 'CEE'}")
            if frame.branch_preference:
                context_parts.append(f"Branch Preference: {frame.branch_preference}")
            context_parts.append("")

            if prediction.safe_options:
                context_parts.append(f"🟢 SAFE OPTIONS ({len(prediction.safe_options)} colleges — high confidence):")
                for i, opt in enumerate(prediction.safe_options, 1):
                    e = opt.evidence
                    context_parts.append(f"  {i}. {e.college_name} — {e.branch}")
                    context_parts.append(f"     Closing Rank: {e.closing_rank} | Match: {e.match_percentage:.0f}% | Year: {e.year}")
                    colleges_for_display.append(self._evidence_to_display(e, opt.band.value))
                context_parts.append("")

            if prediction.target_options:
                context_parts.append(f"🟡 TARGET OPTIONS ({len(prediction.target_options)} colleges — moderate confidence):")
                for i, opt in enumerate(prediction.target_options, 1):
                    e = opt.evidence
                    context_parts.append(f"  {i}. {e.college_name} — {e.branch}")
                    context_parts.append(f"     Closing Rank: {e.closing_rank} | Match: {e.match_percentage:.0f}% | Year: {e.year}")
                    colleges_for_display.append(self._evidence_to_display(e, opt.band.value))
                context_parts.append("")

            if prediction.ambitious_options:
                context_parts.append(f"🔴 AMBITIOUS OPTIONS ({len(prediction.ambitious_options)} colleges — stretch goals):")
                for i, opt in enumerate(prediction.ambitious_options, 1):
                    e = opt.evidence
                    context_parts.append(f"  {i}. {e.college_name} — {e.branch}")
                    context_parts.append(f"     Closing Rank: {e.closing_rank} | Match: {e.match_percentage:.0f}% | Year: {e.year}")
                    colleges_for_display.append(self._evidence_to_display(e, opt.band.value))
                context_parts.append("")

            if prediction.assumptions:
                context_parts.append("Assumptions: " + "; ".join(prediction.assumptions))
            context_parts.append("")

        # ── Build context from web knowledge output ────────────────
        if web_knowledge and web_knowledge.sources_used > 0:
            context_parts.append("=== COLLEGE INFORMATION (WEB KNOWLEDGE) ===")
            for chunk in web_knowledge.chunks:
                source_label = f"[{chunk.college_name}]" if chunk.college_name else ""
                type_label = f"({chunk.page_type})" if chunk.page_type else ""
                # Surface the scrape date so the LLM can qualify its claims
                date_label = ""
                if chunk.scraped_at:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(chunk.scraped_at)
                        date_label = f" — Data from: {dt.strftime('%d %b %Y')}"
                    except Exception:
                        date_label = ""
                context_parts.append(f"{source_label} {type_label}{date_label}")
                context_parts.append(chunk.text)
                context_parts.append("")

            if web_knowledge.summary_points:
                context_parts.append("Key facts:")
                for pt in web_knowledge.summary_points:
                    context_parts.append(f"  • {pt}")
                context_parts.append("")

            if web_knowledge.freshness_note:
                context_parts.append(f"Freshness: {web_knowledge.freshness_note}")
                context_parts.append("")

            # Freshness mix summary for LLM context
            fresh_count = sum(1 for c in web_knowledge.chunks if c.freshness_bucket in ("current", "recent"))
            stale_count = sum(1 for c in web_knowledge.chunks if c.freshness_bucket in ("stale", "archive"))
            if stale_count > 0 and fresh_count > 0:
                context_parts.append(
                    f"Freshness mix: {fresh_count} recent source(s), {stale_count} older source(s). "
                    "Prefer recent data for time-sensitive facts (fees, placements, notices)."
                )
                context_parts.append("")

        # ── Add response instructions ──────────────────────────────
        if context_parts:
            context_parts.append("=== RESPONSE INSTRUCTIONS ===")
            if prediction and prediction.evidence_rows_used > 0:
                context_parts.append("Present colleges grouped by confidence band (Safe → Target → Ambitious).")
                context_parts.append("Use exact closing ranks and match percentages from the data above.")
                context_parts.append("Be encouraging but honest about ambitious options.")
                context_parts.append("Data is from previous year cutoffs; actual cutoffs may vary.")
            if web_knowledge and web_knowledge.sources_used > 0:
                context_parts.append("Use the college information above to answer descriptive questions.")
                context_parts.append("Cite specific facts from the data. Do not invent details.")
                context_parts.append("When a 'Data from' date is shown, qualify your answer with 'as of [date]'.")
                context_parts.append("If sources have mixed freshness dates, prefer the most recent data for time-sensitive facts.")

            return {
                "response_type": "stream",
                "content": "\n".join(context_parts),
                "colleges": colleges_for_display,
                "is_off_topic": False,
                "prediction": prediction.model_dump() if prediction else None,
            }

        # ── Graceful Fallback (No Data Found) ───────────────────────
        return {
            "response_type": "stream",
            "content": "=== RESPONSE INSTRUCTIONS ===\nNo specific data was found for this query in the cutoffs database or the college information knowledge base. Politely and conversationally inform the user that you don't have the specific information they are looking for right now.",
            "colleges": [],
            "is_off_topic": False,
            "prediction": None,
        }

    def _evidence_to_display(self, evidence, band: str) -> Dict[str, Any]:
        """Convert a CutoffEvidenceRow to a display-friendly dict."""
        return {
            "college_name": evidence.college_name,
            "college_code": evidence.college_code,
            "branch": evidence.branch,
            "category": evidence.category,
            "opening_rank": evidence.opening_rank,
            "closing_rank": evidence.closing_rank,
            "year": evidence.year,
            "match_percentage": evidence.match_percentage,
            "seat_type": evidence.seat_type,
            "band": band,
        }

    def _detect_missing_fields(self, frame: RequestFrame) -> List[str]:
        """Detect which essential fields are missing for the given intent."""
        missing = []
        if frame.intent in ("college_prediction", "cutoff_inquiry"):
            if frame.rank is None:
                missing.append("rank")
            if frame.exam is None:
                missing.append("exam")
        return missing

    def _build_greeting_response(self, trace: RequestTrace) -> Dict[str, Any]:
        import random
        
        GREETING_RESPONSES = [
            "Hello! I am RankRoute's AI assistant. I can help you predict your college admissions based on your CEE/JEE rank, or answer questions about fees, hostels, and campus facilities in Assam. How can I help you today?",
            "Hi there! Are you looking for college predictions, cutoff information, or details about a specific college's facilities?",
            "Greetings! I can analyze admission data or fetch college details for you. What do you need help with?"
        ]
        
        return {
            "response_type": "direct",
            "content": random.choice(GREETING_RESPONSES),
            "colleges": [],
            "trace": trace.to_dict(),
        }

    def _build_off_topic_response(self, trace: RequestTrace) -> Dict[str, Any]:
        import random
        
        OFF_TOPIC_RESPONSES = [
            "I'm sorry, I'm specifically trained to answer questions about engineering college admissions, cutoffs, and facilities in Assam. I can't help with that.",
            "That sounds interesting, but my expertise is limited to CEE/JEE cutoffs and college data in Assam. Can I help you with anything related to that?",
            "I don't have information on that topic. Try asking me to predict your colleges based on your rank or to tell you about a college's fee structure."
        ]
        
        return {
            "response_type": "direct",
            "content": random.choice(OFF_TOPIC_RESPONSES),
            "colleges": [],
            "trace": trace.to_dict(),
        }


supreme_orchestrator = SupremeOrchestrator()
