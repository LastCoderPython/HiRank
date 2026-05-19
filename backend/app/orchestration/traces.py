"""
RankRoute V2 — Request Trace Logging

Records every decision the orchestrator makes for observability.

Tracks:
  - request_id
  - detected intent
  - selected route tier
  - activated agents
  - retrieval sources used
  - latency by stage
  - token usage by stage
  - verifier flags
  - fallback reason if triggered
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("rankroute.traces")


@dataclass
class RequestTrace:
    """A single end-to-end trace for one orchestrated request."""

    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    detected_intent: Optional[str] = None
    selected_route: Optional[str] = None
    activated_agents: List[str] = field(default_factory=list)
    retrieval_sources: List[str] = field(default_factory=list)
    stage_latencies: Dict[str, float] = field(default_factory=dict)
    token_usage: Dict[str, int] = field(default_factory=dict)
    verifier_flags: List[str] = field(default_factory=list)
    fallback_reason: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    # Timing helpers
    _stage_start: Optional[float] = field(default=None, repr=False)
    _current_stage: Optional[str] = field(default=None, repr=False)

    def start_stage(self, stage_name: str) -> None:
        self._current_stage = stage_name
        self._stage_start = time.time()

    def end_stage(self) -> None:
        if self._current_stage and self._stage_start:
            elapsed = time.time() - self._stage_start
            self.stage_latencies[self._current_stage] = round(elapsed, 4)
        self._current_stage = None
        self._stage_start = None

    def record_agent(self, agent_name: str) -> None:
        self.activated_agents.append(agent_name)

    def record_tokens(self, stage: str, tokens: int) -> None:
        self.token_usage[stage] = self.token_usage.get(stage, 0) + tokens

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "detected_intent": self.detected_intent,
            "selected_route": self.selected_route,
            "activated_agents": self.activated_agents,
            "retrieval_sources": self.retrieval_sources,
            "stage_latencies": self.stage_latencies,
            "token_usage": self.token_usage,
            "verifier_flags": self.verifier_flags,
            "fallback_reason": self.fallback_reason,
            "total_latency_s": round(
                sum(self.stage_latencies.values()), 4
            ),
        }

    def log(self) -> None:
        """Write the trace summary to the structured logger."""
        logger.info("RequestTrace: %s", self.to_dict())
