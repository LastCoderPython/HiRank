"""
RankRoute V2 — Routing Policy

Classifies each request into the smallest valid execution path.
Avoids waking every agent for every query.

Route categories:
  - prediction_simple: rank/category/branch questions → structured prediction only
  - descriptive_simple: college-info questions → descriptive retrieval only
  - mixed_comparison: comparison queries → prediction + descriptive retrieval
  - recent_update: freshness-sensitive queries → web knowledge with freshness filter
  - ambiguous_needs_clarification: missing essential fields → clarification path
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.orchestration.types import RequestFrame


class RouteCategory(str, Enum):
    PREDICTION_SIMPLE = "prediction_simple"
    DESCRIPTIVE_SIMPLE = "descriptive_simple"
    MIXED_COMPARISON = "mixed_comparison"
    RECENT_UPDATE = "recent_update"
    AMBIGUOUS = "ambiguous_needs_clarification"
    GREETING = "greeting"
    OFF_TOPIC = "off_topic"


class RoutingPolicy:
    """Decides which agents should run for a given request."""

    def resolve(self, frame: "RequestFrame") -> RouteCategory:
        """Map a parsed RequestFrame to the minimum viable route."""

        # Greetings and off-topic bypass all agents
        if frame.intent == "greeting":
            return RouteCategory.GREETING
        if frame.intent == "off_topic":
            return RouteCategory.OFF_TOPIC

        # If user asks about recent notices, updates, etc.
        if frame.intent == "recent_update":
            return RouteCategory.RECENT_UPDATE

        has_rank = frame.rank is not None
        has_college_targets = bool(frame.college_targets)
        needs_web = frame.needs_web_context

        # Pure prediction path
        if frame.intent in ("college_prediction", "cutoff_inquiry") and has_rank:
            return RouteCategory.PREDICTION_SIMPLE

        # Mixed path: Comparison where rank is helpful
        if frame.intent == "comparison" and has_rank:
            return RouteCategory.MIXED_COMPARISON

        # Pure descriptive path
        if needs_web or frame.intent in (
            "college_info", "fee_inquiry", "placement_inquiry",
            "hostel_inquiry", "facility_inquiry", "seat_inquiry", "general_inquiry"
        ):
            return RouteCategory.DESCRIPTIVE_SIMPLE

        # Descriptive with college targets but no rank (fallback)
        if has_college_targets and not has_rank:
            return RouteCategory.DESCRIPTIVE_SIMPLE

        # If we can't determine enough, ask for clarification
        if not has_rank and not has_college_targets:
            return RouteCategory.AMBIGUOUS

        # Fallback: treat as simple prediction if rank exists
        if has_rank:
            return RouteCategory.PREDICTION_SIMPLE

        return RouteCategory.AMBIGUOUS


routing_policy = RoutingPolicy()
