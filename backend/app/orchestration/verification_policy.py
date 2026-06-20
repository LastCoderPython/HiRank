"""
RankRoute V2 — Verification Policy

Controls answer release by checking:
  - No rank claim without structured cutoff evidence.
  - No freshness claim without time-qualified source evidence.
  - No confident answer when key inputs are missing.
  - No merged answer if source authority boundaries are violated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class VerificationVerdict(str, Enum):
    APPROVED = "approved"
    DOWNGRADED = "downgraded"
    CLARIFICATION_REQUIRED = "clarification_required"
    BLOCKED = "blocked"


@dataclass
class VerificationResult:
    verdict: VerificationVerdict
    issues: List[str] = field(default_factory=list)
    downgrade_reason: Optional[str] = None


class VerificationPolicy:
    """Inspects the final evidence bundle before answer release."""

    def verify(
        self,
        intent: str,
        has_cutoff_evidence: bool = False,
        has_web_evidence: bool = False,
        has_freshness_source: bool = False,
        missing_fields: Optional[List[str]] = None,
        source_authority_violated: bool = False,
        out_of_range_gate_triggered: bool = False,
    ) -> VerificationResult:
        issues: List[str] = []

        # Rule: no rank claim without structured evidence
        if intent in ("college_prediction", "cutoff_inquiry") and not has_cutoff_evidence:
            if not out_of_range_gate_triggered:
                issues.append("rank_claim_without_cutoff_evidence")

        # Rule: no freshness claim without qualified source
        if intent == "recent_update" and not has_freshness_source:
            issues.append("freshness_claim_without_source")

        # Rule: no confident answer when required fields are missing
        if missing_fields:
            issues.append(f"missing_required_fields: {', '.join(missing_fields)}")

        # Rule: no merged answer if source authority is violated
        if source_authority_violated:
            issues.append("source_authority_violated")

        # Determine verdict
        if not issues:
            return VerificationResult(verdict=VerificationVerdict.APPROVED)

        if "source_authority_violated" in issues or "rank_claim_without_cutoff_evidence" in issues:
            return VerificationResult(
                verdict=VerificationVerdict.BLOCKED,
                issues=issues,
                downgrade_reason="Cannot make rank claims without authoritative cutoff data.",
            )

        if any("missing_required_fields" in i for i in issues):
            return VerificationResult(
                verdict=VerificationVerdict.CLARIFICATION_REQUIRED,
                issues=issues,
            )

        return VerificationResult(
            verdict=VerificationVerdict.DOWNGRADED,
            issues=issues,
            downgrade_reason="Evidence confidence is insufficient for a definitive answer.",
        )


verification_policy = VerificationPolicy()
