from pydantic import BaseModel
from typing import Optional


class CEECutoff(BaseModel):
    college_code: str
    college_name: str
    branch: str
    category: str
    opening_rank: int
    closing_rank: int
    year: int
    seat_type: str
    quota: Optional[str] = None


class JEECutoff(BaseModel):
    institute_code: str
    institute_name: str
    branch: str
    category: str
    opening_rank: int
    closing_rank: int
    year: int
    quota: str
    seat_type: str


class CollegeMetadata(BaseModel):
    college_code: str
    college_name: str
    location: str
    type: str
    established: Optional[int] = None
    avg_fees: Optional[str] = None
    placement_rate: Optional[str] = None
    naac_grade: Optional[str] = None
    website: Optional[str] = None


class BranchInfo(BaseModel):
    branch_code: str
    branch_name: str
    total_seats: Optional[int] = None
    avg_package: Optional[str] = None
    description: Optional[str] = None
