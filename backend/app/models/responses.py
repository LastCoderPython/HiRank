from pydantic import BaseModel, Field
from typing import Optional, List, Dict


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


class SimulatedOption(BaseModel):
    college_name: str
    college_code: str = ""
    branch: str
    closing_rank: int
    match_percentage: float
    band: str
    is_unlocked: bool = False


class SimulationResponse(BaseModel):
    current_rank: int
    target_rank: int
    category: str
    exam: str
    current_options: List[SimulatedOption]
    target_options: List[SimulatedOption]
    newly_unlocked: List[SimulatedOption]
    summary: str


class ComparisonMetric(BaseModel):
    label: str
    values: Dict[str, str]
    source: Optional[str] = None


class ComparisonResponse(BaseModel):
    colleges: List[str]
    branch: Optional[str] = None
    metrics: List[ComparisonMetric]
    has_data: bool
