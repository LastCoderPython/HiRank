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
from typing import List, Optional

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

        # Check prediction evidence for rank-related intents.
        # IMPORTANT: cutoff_inquiry with college targets but NO rank is a
        # descriptive lookup ("what are the cutoffs for AEC?"), NOT a prediction.
        # Only require rank/exam when the user is asking for a PERSONAL prediction.
        is_personal_prediction = (
            frame.intent in ("college_prediction", "cutoff_inquiry")
            and frame.rank is not None  # user provided their rank → personal prediction
        )
        is_descriptive_cutoff_lookup = (
            frame.intent == "cutoff_inquiry"
            and frame.rank is None
            and bool(frame.college_targets)  # user named a college → historical lookup
        )

        has_cutoff_evidence = (
            prediction is not None and prediction.evidence_rows_used > 0
        )

        # BUG-01/09 FIX: Detect the out-of-range gate case.
        # When the cutoff engine ran but returned 0 results because the user's
        # rank exceeds every closing rank in the dataset, that is a VALID and
        # COMPLETE engine response — not a verification failure.
        # The honest-framing path in _synthesize will handle the response.
        out_of_range_gate_triggered = (
            prediction is not None
            and prediction.evidence_rows_used == 0
            and bool(getattr(prediction, "assumptions", None))
            and any(
                "exceeds the closing rank" in a
                for a in (prediction.assumptions or [])
            )
        )

        if is_personal_prediction and not out_of_range_gate_triggered:
            if not has_cutoff_evidence:
                issues.append("rank_claim_without_cutoff_evidence")
            # Do NOT add to missing_fields — rank is already present
        elif frame.intent == "college_prediction" and frame.rank is None:
            # Pure prediction intent with no rank → ask for rank
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
            frame.intent, has_cutoff_evidence, has_web_evidence,
            out_of_range_gate_triggered=out_of_range_gate_triggered,
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
            out_of_range_gate_triggered=out_of_range_gate_triggered,
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
        out_of_range_gate_triggered: bool = False,
    ) -> bool:
        """Check if source authority rules are violated.

        Key rule: a prediction answer MUST come from cutoff_truth,
        not from web_docs alone. Web docs may enrich but not override.

        Comparison and descriptive cutoff lookups are NEVER blocked
        by source authority — they are designed to use whatever data
        is available.

        Out-of-range gate responses are also never blocked — the engine
        ran correctly and found no eligible colleges.
        """
        # Out-of-range gate: prediction ran, found no results → approve for honest framing
        if out_of_range_gate_triggered:
            return False

        # Comparison and descriptive intents are never blocked by source authority
        if intent in ("comparison", "general_inquiry", "seat_inquiry",
                      "branch_inquiry", "recent_update"):
            return False

        # cutoff_inquiry without a rank is a descriptive lookup — not blocked
        # (handled upstream by is_descriptive_cutoff_lookup)
        required_sources = source_policy.get_required_sources(intent)

        if AuthoritativeSource.CUTOFF_TRUTH in required_sources and not has_cutoff:
            # Prediction intent requires cutoff evidence
            return True

        return False


verifier_agent = VerifierAgent()
