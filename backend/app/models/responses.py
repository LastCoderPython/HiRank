from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class CollegeInfo(BaseModel):
    college_name: str
    college_code: str = ""
    branch: str
    category: str
    opening_rank: int = 0
    closing_rank: int
    year: int
    match_percentage: float
    seat_type: str
    band: Optional[str] = None
    location: Optional[str] = None
    placement_rate: Optional[str] = None
    avg_fees: Optional[str] = None


class CollegeListResponse(BaseModel):
    colleges: List[CollegeInfo]
    total: int
    query_params: dict


class ChatStreamingResponse(BaseModel):
    session_id: str
    token: Optional[str] = None
    colleges: Optional[List[CollegeInfo]] = None
    done: bool = False


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class HealthResponse(BaseModel):
    status: str
    version: str
    vector_db_status: str
    llm_status: str
