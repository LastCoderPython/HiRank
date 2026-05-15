from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class StudentProfile(BaseModel):
    student_id: str = Field(default="guest")
    rank: Optional[int] = None
    category: Optional[str] = "General"
    preferred_branches: List[str] = Field(default_factory=list)
    budget_tier: Optional[str] = None
    location_preference: Optional[str] = None


class AgentPlanRequest(BaseModel):
    goal: str = Field(..., min_length=5)
    collection: str = Field(default="cee")
    student_profile: StudentProfile = Field(default_factory=StudentProfile)


class AgentTaskView(BaseModel):
    task_id: str
    agent: str
    objective: str
    depends_on: List[str] = Field(default_factory=list)


class AgentPlanResponse(BaseModel):
    plan_id: str
    tasks: List[AgentTaskView]


class AgentExecuteRequest(BaseModel):
    goal: str = Field(..., min_length=5)
    collection: str = Field(default="cee")
    student_profile: StudentProfile = Field(default_factory=StudentProfile)


class TaskExecutionView(BaseModel):
    task_id: str
    agent: str
    success: bool
    confidence: float
    summary: str
    attempts: int
    warnings: List[str] = Field(default_factory=list)


class CitationView(BaseModel):
    source_id: str
    title: str
    url: Optional[str] = None
    excerpt: str


class RecommendationView(BaseModel):
    college: str
    branch: str
    category: str
    year: Optional[int] = None
    confidence: float
    reasoning: str


class AgentExecuteResponse(BaseModel):
    overall_confidence: float
    tasks: List[TaskExecutionView]
    recommendations: List[RecommendationView]
    citations: List[CitationView]


class MemoryNoteRequest(BaseModel):
    note: str = Field(..., min_length=3)
    source: str = Field(default="user")


class MemoryPreferencesRequest(BaseModel):
    preferences: Dict[str, str]


class MemoryResponse(BaseModel):
    student_id: str
    preferences: Dict[str, str]
    notes: List[Dict[str, str]]
    last_context: Optional[str] = None
