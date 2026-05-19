"""
RankRoute V2 — Source Authority Policy

Defines which data source is authoritative for each class of question.

Rules:
  - cutoff_truth: authoritative for rank prediction, eligibility,
    and safe/target/ambitious classification.
  - college_web_docs: authoritative for placements, hostel, fees,
    facilities, and notices.
  - Mixed answers may combine both, but descriptive web data must
    never override structured admission truth.
"""

from __future__ import annotations

from enum import Enum
from typing import List


class AuthoritativeSource(str, Enum):
    CUTOFF_TRUTH = "cutoff_truth"
    COLLEGE_WEB_DOCS = "college_web_docs"


# Maps intent types to authoritative sources
_SOURCE_MAP = {
    "college_prediction": AuthoritativeSource.CUTOFF_TRUTH,
    "cutoff_inquiry": AuthoritativeSource.CUTOFF_TRUTH,
    "branch_inquiry": AuthoritativeSource.CUTOFF_TRUTH,
    "fee_inquiry": AuthoritativeSource.COLLEGE_WEB_DOCS,
    "placement_inquiry": AuthoritativeSource.COLLEGE_WEB_DOCS,
    "hostel_inquiry": AuthoritativeSource.COLLEGE_WEB_DOCS,
    "facility_inquiry": AuthoritativeSource.COLLEGE_WEB_DOCS,
    "college_info": AuthoritativeSource.COLLEGE_WEB_DOCS,
    "recent_update": AuthoritativeSource.COLLEGE_WEB_DOCS,
    "comparison": None,  # both sources needed
}


class SourcePolicy:
    """Controls which data source may answer which type of question."""

    def get_authoritative_source(self, intent: str) -> AuthoritativeSource | None:
        """Return the authoritative source for the given intent.
        Returns None for mixed intents that require both sources."""
        return _SOURCE_MAP.get(intent)

    def get_required_sources(self, intent: str) -> List[AuthoritativeSource]:
        """Return all sources required to answer a query of this intent."""
        source = self.get_authoritative_source(intent)
        if source is not None:
            return [source]
        # For mixed intents (comparison), both sources are required
        return [AuthoritativeSource.CUTOFF_TRUTH, AuthoritativeSource.COLLEGE_WEB_DOCS]

    def validate_answer_sources(
        self, intent: str, sources_used: List[AuthoritativeSource]
    ) -> bool:
        """Verify that the answer does not violate source authority.
        
        Key rule: a rank prediction claim must NOT come from web docs.
        """
        authoritative = self.get_authoritative_source(intent)
        if authoritative is None:
            # Mixed intent — both are acceptable
            return True
        return authoritative in sources_used


source_policy = SourcePolicy()
