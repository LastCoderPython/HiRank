from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ChatMessage(BaseModel):
    role: str = Field(..., description="Message role: user or assistant")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    message: str = Field(..., description="User message/query")
    session_id: Optional[str] = Field(None, description="Session identifier")
    history: Optional[List[ChatMessage]] = Field(
        default=[],
        description="Chat history for context"
    )


class CollegePrediction(BaseModel):
    college_name: str
    college_code: str
    branch: str
    category: str
    opening_rank: int
    closing_rank: int
    year: int
    match_percentage: float
    seat_type: str


class StreamToken(BaseModel):
    token: str


class ChatResponse(BaseModel):
    response: str
    colleges: Optional[List[CollegePrediction]] = None
    session_id: str
    timestamp: datetime = Field(default_factory=datetime.now)


class CollegeFilterRequest(BaseModel):
    rank: int = Field(..., ge=1, description="User's rank")
    category: str = Field(default="General", description="Category")
    branch: Optional[str] = Field(None, description="Branch preference")
    exam: str = Field(default="CEE", description="Exam type: CEE or JEE")
    limit: int = Field(default=10, ge=1, le=50)


class ParsedQuery(BaseModel):
    intent: str
    exam: Optional[str] = None
    rank: Optional[int] = None
    category: str = "General"
    branch: Optional[str] = None
    year: Optional[int] = None
    raw_query: str
    college_code: Optional[str] = None
