from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AgentName(str, Enum):
    DATA_COLLECTION = "data_collection"
    PDF_PARSER = "pdf_parser"
    SOCIAL_INTEL = "social_intelligence"
    PLACEMENT_ANALYSIS = "placement_analysis"
    DYNAMIC_UPDATES = "dynamic_updates"
    SEARCH_RESEARCH = "search_research"
    VERIFICATION = "verification"
    RECOMMENDATION = "recommendation"
    STUDENT_MEMORY = "student_memory"
    HYBRID_RAG = "hybrid_rag"


@dataclass
class AgentTask:
    id: str
    agent: AgentName
    objective: str
    payload: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)


@dataclass
class Citation:
    source_id: str
    title: str
    url: Optional[str]
    excerpt: str


@dataclass
class AgentResult:
    task_id: str
    agent: AgentName
    success: bool
    confidence: float
    summary: str
    data: Dict[str, Any] = field(default_factory=dict)
    citations: List[Citation] = field(default_factory=list)
    attempts: int = 1
    warnings: List[str] = field(default_factory=list)
