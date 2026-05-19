"""
RankRoute V2 — Orchestration Types

Shared data contracts for the orchestration layer and specialist agents.
Each agent returns structured JSON via Pydantic models, not prose.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from enum import Enum


# ─── Request Frame ────────────────────────────────────────────────────
# The structured representation of a parsed user query that the
# orchestrator passes through the policy layer.

class RequestFrame(BaseModel):
    """Structured request context produced by the intent parser."""
    intent: str = "general_inquiry"
    exam: Optional[str] = None
    rank: Optional[int] = None
    category: str = "General"
    branch_preference: Optional[str] = None
    college_targets: List[str] = Field(default_factory=list)
    needs_web_context: bool = False
    confidence: float = 1.0
    raw_query: str = ""


# ─── Agent Output Contracts ──────────────────────────────────────────

class IntentAgentOutput(BaseModel):
    """Output of the Intent & Parameters Agent."""
    intent: str
    exam: Optional[str] = None
    rank: Optional[int] = None
    category: str = "General"
    branch_preference: Optional[str] = None
    college_targets: List[str] = Field(default_factory=list)
    needs_web_context: bool = False
    confidence: float = 1.0


class CutoffEvidenceRow(BaseModel):
    """A single evidence row from structured cutoff truth."""
    college_name: str
    college_code: str = ""
    branch: str
    category: str
    opening_rank: int = 0
    closing_rank: int = 0
    year: int = 2024
    seat_type: str = "Government"
    exam: str = "CEE"
    quota: Optional[str] = None
    match_percentage: float = 0.0


class PredictionBand(str, Enum):
    SAFE = "safe"
    TARGET = "target"
    AMBITIOUS = "ambitious"


class PredictionOption(BaseModel):
    """A single college+branch option with its confidence band."""
    band: PredictionBand
    evidence: CutoffEvidenceRow
    reason: str = ""


class PredictionAgentOutput(BaseModel):
    """Output of the Structured Prediction Agent."""
    safe_options: List[PredictionOption] = Field(default_factory=list)
    target_options: List[PredictionOption] = Field(default_factory=list)
    ambitious_options: List[PredictionOption] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    evidence_rows_used: int = 0


class WebKnowledgeChunk(BaseModel):
    """A single retrieved web knowledge chunk."""
    text: str
    college_name: str = ""
    page_type: str = ""
    source_url: Optional[str] = None
    is_official: bool = True
    freshness_bucket: Optional[str] = None
    relevance_score: float = 0.0


class WebKnowledgeOutput(BaseModel):
    """Output of the Web Knowledge Agent."""
    chunks: List[WebKnowledgeChunk] = Field(default_factory=list)
    summary_points: List[str] = Field(default_factory=list)
    sources_used: int = 0
    freshness_note: Optional[str] = None


class VerifierOutput(BaseModel):
    """Output of the Verifier Agent."""
    approved: bool = True
    issues: List[str] = Field(default_factory=list)
    downgrade_reason: Optional[str] = None
    missing_fields: List[str] = Field(default_factory=list)
