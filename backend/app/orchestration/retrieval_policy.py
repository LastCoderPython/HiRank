"""
RankRoute V2 — Retrieval Policy

Constrains document retrieval behaviour:
  - Apply metadata filters before vector search.
  - Prefer official documents over unofficial sources.
  - Use freshness-aware retrieval for recent-update queries.
  - Deduplicate near-identical chunks before final synthesis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RetrievalConstraints:
    """The filtering and retrieval parameters for a single request."""
    metadata_filters: Dict[str, Any] = field(default_factory=dict)
    prefer_official: bool = True
    freshness_required: bool = False
    max_chunks: int = 5
    deduplicate: bool = True


class RetrievalPolicy:
    """Builds retrieval constraints based on query parameters."""

    def build_constraints(
        self,
        college_targets: Optional[List[str]] = None,
        page_types: Optional[List[str]] = None,
        freshness_required: bool = False,
        max_chunks: int = 5,
    ) -> RetrievalConstraints:
        filters: Dict[str, Any] = {}

        if college_targets and len(college_targets) == 1:
            filters["college_name"] = college_targets[0]
        elif college_targets and len(college_targets) > 1:
            filters["college_name"] = {"$in": college_targets}

        if page_types and len(page_types) == 1:
            filters["page_type"] = page_types[0]
        elif page_types and len(page_types) > 1:
            filters["page_type"] = {"$in": page_types}

        return RetrievalConstraints(
            metadata_filters=filters,
            prefer_official=True,
            freshness_required=freshness_required,
            max_chunks=max_chunks,
            deduplicate=True,
        )


retrieval_policy = RetrievalPolicy()
