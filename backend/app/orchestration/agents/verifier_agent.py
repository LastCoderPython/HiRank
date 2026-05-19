"""
RankRoute V2 — Verifier Agent

Validates the final evidence bundle before answer release.
Uses the VerificationPolicy + SourcePolicy to check:
  - No rank claim without structured cutoff evidence
  - No freshness claim without time-qualified sources
  - No mixed answer violating source authority boundaries
  - Proper handling of missing required fields

Returns a VerifierOutput with approval/downgrade/block decision.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.orchestration.types import (
    PredictionAgentOutput,
    RequestFrame,
    VerifierOutput,
    WebKnowledgeOutput,
)
from app.orchestration.verification_policy import verification_policy, VerificationVerdict
from app.orchestration.source_policy import source_policy, AuthoritativeSource

logger = logging.getLogger("rankroute.agents.verifier")


class VerifierAgent:
    """
    Validates evidence bundles before the orchestrator streams answers.

    This agent does NOT generate content. It only inspects the outputs
    of other agents and decides whether the answer should be:
      - APPROVED: streamed as-is
      - DOWNGRADED: streamed with a confidence caveat
      - CLARIFICATION_REQUIRED: ask the user for more info
      - BLOCKED: refuse to answer (insufficient evidence)
    """

    async def run(
        self,
        frame: RequestFrame,
        prediction: Optional[PredictionAgentOutput] = None,
        web_knowledge: Optional[WebKnowledgeOutput] = None,
    ) -> VerifierOutput:
        """Verify the evidence bundle for a given request."""
        issues: List[str] = []
        missing_fields: List[str] = []

        # Check prediction evidence for rank-related intents
        has_cutoff_evidence = (
            prediction is not None and prediction.evidence_rows_used > 0
        )
        if frame.intent in ("college_prediction", "cutoff_inquiry"):
            if not has_cutoff_evidence:
                issues.append("rank_claim_without_cutoff_evidence")
            if frame.rank is None:
                missing_fields.append("rank")
            if frame.exam is None:
                missing_fields.append("exam")

        # Check web evidence for descriptive intents
        has_web_evidence = (
            web_knowledge is not None and web_knowledge.sources_used > 0
        )
        if frame.intent in ("fee_inquiry", "placement_inquiry", "hostel_inquiry",
                            "facility_inquiry", "college_info"):
            if not has_web_evidence:
                issues.append("descriptive_query_without_web_evidence")

        # Check freshness for recent-update intents
        has_freshness = (
            web_knowledge is not None and web_knowledge.freshness_note is not None
            and "recent document" in (web_knowledge.freshness_note or "").lower()
        )
        if frame.intent == "recent_update" and not has_freshness:
            issues.append("freshness_claim_without_source")

        # Check source authority
        source_violated = self._check_source_authority(
            frame.intent, has_cutoff_evidence, has_web_evidence
        )
        if source_violated:
            issues.append("source_authority_violated")

        # Determine verdict using the verification policy
        policy_result = verification_policy.verify(
            intent=frame.intent,
            has_cutoff_evidence=has_cutoff_evidence,
            has_web_evidence=has_web_evidence,
            has_freshness_source=has_freshness,
            missing_fields=missing_fields if missing_fields else None,
            source_authority_violated=source_violated,
        )

        return VerifierOutput(
            approved=policy_result.verdict == VerificationVerdict.APPROVED,
            issues=policy_result.issues,
            downgrade_reason=policy_result.downgrade_reason,
            missing_fields=missing_fields,
        )

    def _check_source_authority(
        self,
        intent: str,
        has_cutoff: bool,
        has_web: bool,
    ) -> bool:
        """Check if source authority rules are violated.

        Key rule: a prediction answer MUST come from cutoff_truth,
        not from web_docs alone. Web docs may enrich but not override.
        """
        required_sources = source_policy.get_required_sources(intent)

        if AuthoritativeSource.CUTOFF_TRUTH in required_sources and not has_cutoff:
            # Prediction intent requires cutoff evidence
            return True

        return False


verifier_agent = VerifierAgent()
