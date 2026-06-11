"""
College Compare API — side-by-side comparison of colleges.

GET /api/colleges/compare?colleges=AEC,JEC&branch=CSE

Returns structured metrics (fee, placement, hostel, seats) for each college.
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional

from app.models.responses import ComparisonResponse, ComparisonMetric
from app.services.college_info_service import college_info_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/colleges", tags=["compare"])


@router.get("/compare", response_model=ComparisonResponse)
async def compare_colleges(
    colleges: str = Query(..., description="Comma-separated college codes (e.g. AEC,JEC)"),
    branch: Optional[str] = Query(None, description="Optional branch filter (e.g. CSE)"),
):
    try:
        codes = [c.strip().upper() for c in colleges.split(",") if c.strip()]
        if len(codes) < 2:
            raise HTTPException(status_code=422, detail="Provide at least 2 college codes")

        metrics: List[ComparisonMetric] = []

        # 1. Fee structure (first year total)
        fee_values = {}
        for code in codes:
            fees = college_info_service.get_fee_structure(code)
            if fees:
                filtered = [f for f in fees if not branch or branch.upper() in f.get("program", "").upper()]
                entry = filtered[0] if filtered else fees[0]
                fee_values[code] = f"\u20B9{entry.get('total_first_year', 'N/A')}"
            else:
                fee_values[code] = "N/A"
        metrics.append(ComparisonMetric(label="Fee (First Year)", values=fee_values, source="fee_structure.csv"))

        # 2. Placement stats (avg package, filtered by branch)
        avg_pkg_values = {}
        highest_pkg_values = {}
        placement_pct_values = {}
        for code in codes:
            placements = college_info_service.get_placement_stats(code, branch)
            if placements:
                avg = placements[0].get("avg_package_lpa", "N/A")
                highest = placements[0].get("highest_package_lpa", "N/A")
                pct = placements[0].get("placement_percentage", "N/A")
                avg_pkg_values[code] = f"\u20B9{avg} LPA" if avg != "N/A" else "N/A"
                highest_pkg_values[code] = f"\u20B9{highest} LPA" if highest != "N/A" else "N/A"
                placement_pct_values[code] = f"{pct}%" if pct != "N/A" else "N/A"
            else:
                avg_pkg_values[code] = "N/A"
                highest_pkg_values[code] = "N/A"
                placement_pct_values[code] = "N/A"

        metrics.append(ComparisonMetric(label="Avg Package", values=avg_pkg_values, source="placement_stats.csv"))
        metrics.append(ComparisonMetric(label="Highest Package", values=highest_pkg_values, source="placement_stats.csv"))
        metrics.append(ComparisonMetric(label="Placement Rate", values=placement_pct_values, source="placement_stats.csv"))

        # 3. Hostel availability
        hostel_values = {}
        for code in codes:
            facilities = college_info_service.get_facilities(code)
            if facilities:
                boys = facilities.get("hostel_boys", "0")
                girls = facilities.get("hostel_girls", "0")
                hostel_values[code] = f"Yes ({boys}B/{girls}G)" if boys != "0" or girls != "0" else "No"
            else:
                hostel_values[code] = "N/A"
        metrics.append(ComparisonMetric(label="Hostel", values=hostel_values, source="facilities.csv"))

        # 4. Seats (filtered by branch)
        seats_values = {}
        for code in codes:
            matrix = college_info_service.get_seat_matrix(code, branch)
            if matrix:
                branch_key = branch or list(matrix.keys())[0]
                entry = matrix.get(branch_key, {})
                seats_values[code] = entry.get("total_seats", "N/A")
            else:
                seats_values[code] = "N/A"
        metrics.append(ComparisonMetric(label="Seats", values=seats_values, source="seat_matrix.csv"))

        # 5. Campus size
        campus_values = {}
        for code in codes:
            facilities = college_info_service.get_facilities(code)
            if facilities and facilities.get("campus_area"):
                campus_values[code] = f"{facilities['campus_area']} acres"
            else:
                campus_values[code] = "N/A"
        metrics.append(ComparisonMetric(label="Campus", values=campus_values, source="facilities.csv"))

        has_data = any(v != "N/A" for m in metrics for v in m.values.values())

        return ComparisonResponse(colleges=codes, branch=branch, metrics=metrics, has_data=has_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error comparing colleges: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
