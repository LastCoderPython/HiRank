"""
RankRoute V2 — Metadata Filters

Builds Chroma-compatible metadata filter dicts for college_web_docs retrieval.
Chroma supports $and, $or, $in, $contains, $eq, $ne, $gt, $gte, $lt, $lte
operators for metadata filtering before vector search.

Used by the WebKnowledgeAgent and RetrievalPolicy.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_college_filter(
    college_names: Optional[List[str]] = None,
    page_types: Optional[List[str]] = None,
    is_official: Optional[bool] = None,
    freshness_buckets: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Build a Chroma `where` filter dict for college_web_docs retrieval.

    Args:
        college_names: Filter to specific colleges (e.g., ["AEC", "JEC"])
        page_types: Filter to page types (e.g., ["placement", "hostel", "fees"])
        is_official: Filter to official sources only
        freshness_buckets: Filter by freshness (e.g., ["current", "recent"])

    Returns:
        A Chroma-compatible where filter dict, or None if no filters apply.

    Examples:
        >>> build_college_filter(college_names=["JEC"], page_types=["hostel"])
        {"$and": [{"college_name": "JEC"}, {"page_type": "hostel"}]}

        >>> build_college_filter(college_names=["AEC"], is_official=True, page_types=["placement"])
        {"$and": [{"college_name": "AEC"}, {"is_official": True}, {"page_type": "placement"}]}
    """
    conditions: List[Dict[str, Any]] = []

    # College name filter
    if college_names:
        if len(college_names) == 1:
            conditions.append({"college_name": college_names[0]})
        else:
            conditions.append({"college_name": {"$in": college_names}})

    # Page type filter
    if page_types:
        if len(page_types) == 1:
            conditions.append({"page_type": page_types[0]})
        else:
            conditions.append({"page_type": {"$in": page_types}})

    # Official source filter
    if is_official is not None:
        conditions.append({"is_official": is_official})

    # Freshness filter
    if freshness_buckets:
        if len(freshness_buckets) == 1:
            conditions.append({"freshness_bucket": freshness_buckets[0]})
        else:
            conditions.append({"freshness_bucket": {"$in": freshness_buckets}})

    # Combine conditions
    if not conditions:
        return None
    elif len(conditions) == 1:
        return conditions[0]
    else:
        return {"$and": conditions}


def intent_to_page_types(intent: str) -> Optional[List[str]]:
    """Map a query intent to relevant page_type metadata values."""
    mapping = {
        "fee_inquiry": ["fees", "fee_structure"],
        "placement_inquiry": ["placement", "placements", "placement_stats"],
        "hostel_inquiry": ["hostel", "accommodation", "campus_life"],
        "facility_inquiry": ["facilities", "infrastructure", "campus"],
        "college_info": ["about", "overview", "general"],
        "recent_update": ["notice", "admission_notice", "update", "announcement"],
        "branch_inquiry": ["branch_info", "programs", "courses"],
        "seat_inquiry": ["seat_matrix", "intake"],
    }
    return mapping.get(intent)
