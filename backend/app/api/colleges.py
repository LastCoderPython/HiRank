from typing import List
from fastapi import APIRouter, HTTPException, Query
from app.config import settings
from app.models.responses import CollegeListResponse, CollegeInfo, SimulationResponse, SimulatedOption
from app.retrieval.cutoff_engine import cutoff_engine, PredictionResult, PredictionBundle
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["colleges"])


@router.get("/colleges", response_model=CollegeListResponse)
async def get_colleges(
    rank: int = Query(..., ge=1, description="User's rank"),
    category: str = Query("General", pattern="^(General|OBC|SC|ST|EWS)$", description="Category"),
    branch: str = Query(None, description="Branch filter"),
    exam: str = Query("CEE", pattern="^(CEE|JEE)$", description="Exam type"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
):
    try:
        colleges_raw = cutoff_engine.get_colleges_list(
            rank=rank,
            category=category,
            exam=exam,
            branch=branch,
            limit=limit,
        )

        colleges = []
        for c in colleges_raw:
            colleges.append(CollegeInfo(
                college_name=c["college_name"],
                college_code=c.get("college_code", ""),
                branch=c["branch"],
                category=c["category"],
                opening_rank=c.get("opening_rank", 0),
                closing_rank=c["closing_rank"],
                year=c["year"],
                match_percentage=c["match_percentage"],
                seat_type=c.get("seat_type", "Government"),
                band=c.get("band"),
            ))

        return CollegeListResponse(
            colleges=colleges,
            total=len(colleges),
            query_params={
                "rank": rank,
                "category": category,
                "branch": branch,
                "exam": exam,
                "limit": limit
            }
        )
    except Exception as e:
        logger.error("Error getting colleges: %s", e)
        raise HTTPException(status_code=500, detail=str(e) if settings.debug else "Internal server error")


def _predictions_to_options(bundle: PredictionBundle) -> List[SimulatedOption]:
    options = []
    for r in bundle.safe_options:
        options.append(SimulatedOption(
            college_name=r.college_name, college_code=r.college_code,
            branch=r.branch, closing_rank=r.closing_rank,
            match_percentage=r.match_percentage, band="safe",
        ))
    for r in bundle.target_options:
        options.append(SimulatedOption(
            college_name=r.college_name, college_code=r.college_code,
            branch=r.branch, closing_rank=r.closing_rank,
            match_percentage=r.match_percentage, band="target",
        ))
    for r in bundle.ambitious_options:
        options.append(SimulatedOption(
            college_name=r.college_name, college_code=r.college_code,
            branch=r.branch, closing_rank=r.closing_rank,
            match_percentage=r.match_percentage, band="ambitious",
        ))
    return options


@router.get("/colleges/simulate", response_model=SimulationResponse)
async def simulate_rank(
    current_rank: int = Query(..., ge=1, description="Current rank"),
    target_rank: int = Query(..., ge=1, description="Target/what-if rank"),
    category: str = Query("General", pattern="^(General|OBC|SC|ST|EWS)$"),
    exam: str = Query("CEE", pattern="^(CEE|JEE)$"),
    branch: str = Query(None, description="Branch filter"),
    limit: int = Query(10, ge=1, le=50),
):
    try:
        current: PredictionBundle = cutoff_engine.predict(
            rank=current_rank, category=category, exam=exam,
            branch=branch, limit=limit,
        )
        target: PredictionBundle = cutoff_engine.predict(
            rank=target_rank, category=category, exam=exam,
            branch=branch, limit=limit,
        )

        cur_options = _predictions_to_options(current)
        tgt_options = _predictions_to_options(target)

        # Determine newly unlocked: options in target with band in (safe|target)
        # that are NOT in current options with band in (safe|target)
        cur_keys = {(o.college_name, o.branch)
                    for o in cur_options if o.band in ("safe", "target")}
        newly_unlocked = [
            o for o in tgt_options
            if o.band in ("safe", "target")
            and (o.college_name, o.branch) not in cur_keys
        ]

        n_unlocked = len(newly_unlocked)
        n_safe = sum(1 for o in tgt_options if o.band == "safe")
        n_target = sum(1 for o in tgt_options if o.band == "target")
        summary = (
            f"Improving from rank {current_rank} to {target_rank} "
            f"unlocks {n_unlocked} new {'college' if n_unlocked == 1 else 'colleges'} "
            f"({n_safe} safe, {n_target} target)."
        )

        return SimulationResponse(
            current_rank=current_rank,
            target_rank=target_rank,
            category=category,
            exam=exam,
            current_options=cur_options,
            target_options=tgt_options,
            newly_unlocked=newly_unlocked,
            summary=summary,
        )
    except Exception as e:
        logger.error("Error simulating rank: %s", e)
        raise HTTPException(status_code=500, detail=str(e) if settings.debug else "Internal server error")
