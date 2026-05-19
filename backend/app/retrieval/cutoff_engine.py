"""
RankRoute V2 — Deterministic Cutoff Engine

The core trust engine for rank-based admission prediction.
Queries structured cutoff truth (CSV data), NOT Chroma.

Responsibilities:
  - Load and normalize historical cutoff data from CSV files.
  - Filter by exam, category, branch, and year.
  - Compare user rank with historical closing ranks.
  - Generate safe / target / ambitious classifications.
  - Return the evidence rows that support every prediction.

Design principles (from V2 plan):
  - Deterministic logic first, LLM second.
  - No semantic search for rank prediction — only structured filtering.
  - Every prediction is auditable via evidence rows.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from app.config import settings

logger = logging.getLogger("rankroute.cutoff_engine")


# ─── Data Models ──────────────────────────────────────────────────────

@dataclass
class CutoffRecord:
    """A single normalized cutoff record from the structured truth layer."""
    college_name: str
    college_code: str
    branch: str
    category: str
    opening_rank: int
    closing_rank: int
    year: int
    seat_type: str
    exam: str
    quota: Optional[str] = None
    round: Optional[str] = None


@dataclass
class PredictionResult:
    """A single college+branch option with its confidence band."""
    college_name: str
    college_code: str
    branch: str
    category: str
    opening_rank: int
    closing_rank: int
    year: int
    seat_type: str
    exam: str
    quota: Optional[str] = None
    band: str = "target"           # safe | target | ambitious
    match_percentage: float = 0.0
    reason: str = ""


@dataclass
class PredictionBundle:
    """Complete prediction output from the cutoff engine."""
    safe_options: List[PredictionResult] = field(default_factory=list)
    target_options: List[PredictionResult] = field(default_factory=list)
    ambitious_options: List[PredictionResult] = field(default_factory=list)
    evidence_rows_used: int = 0
    assumptions: List[str] = field(default_factory=list)
    query_params: Dict[str, Any] = field(default_factory=dict)


# ─── Cutoff Engine ────────────────────────────────────────────────────

class CutoffEngine:
    """
    Deterministic admission prediction engine.

    Loads CEE and JEE cutoff CSVs into pandas DataFrames and provides
    structured, auditable predictions based on exact filtering and
    rank comparison — no embeddings, no semantic search.
    """

    def __init__(self):
        self._cee_df: Optional[pd.DataFrame] = None
        self._jee_df: Optional[pd.DataFrame] = None
        self._data_loaded: bool = False
        self._load_data()

    # ── Data Loading ──────────────────────────────────────────────────

    def _load_data(self) -> None:
        """Load and normalize cutoff data from CSV files."""
        cee_path = Path(settings.cee_data_path)
        jee_path = Path(settings.jee_data_path)

        if cee_path.exists():
            self._cee_df = self._normalize_df(pd.read_csv(cee_path), exam="CEE")
            logger.info("CutoffEngine: loaded %d CEE records", len(self._cee_df))
        else:
            logger.warning("CutoffEngine: CEE CSV not found at %s", cee_path)
            self._cee_df = pd.DataFrame()

        if jee_path.exists():
            self._jee_df = self._normalize_df(pd.read_csv(jee_path), exam="JEE")
            logger.info("CutoffEngine: loaded %d JEE records", len(self._jee_df))
        else:
            logger.warning("CutoffEngine: JEE CSV not found at %s", jee_path)
            self._jee_df = pd.DataFrame()

        self._data_loaded = True

    def _normalize_df(self, df: pd.DataFrame, exam: str) -> pd.DataFrame:
        """Clean column names, fill NAs, cast numeric columns."""
        df.columns = df.columns.str.strip().str.lower()

        # Standardize column names
        rename_map = {
            "college": "college_name",
            "institute": "college_name",
            "institute_name": "college_name",
            "branch_name": "branch",
            "course": "branch",
            "open_rank": "opening_rank",
            "close_rank": "closing_rank",
            "op_rank": "opening_rank",
            "cl_rank": "closing_rank",
        }
        df = df.rename(columns=rename_map)

        # Ensure required columns exist
        for col in ["college_name", "college_code", "branch", "category",
                     "opening_rank", "closing_rank", "year", "seat_type"]:
            if col not in df.columns:
                df[col] = ""

        if "quota" not in df.columns:
            df["quota"] = ""
        if "round" not in df.columns:
            df["round"] = ""
        if "exam" not in df.columns:
            df["exam"] = exam

        # Fill NAs and cast types
        df["college_name"] = df["college_name"].fillna("").astype(str).str.strip()
        df["college_code"] = df["college_code"].fillna("").astype(str).str.strip()
        df["branch"] = df["branch"].fillna("").astype(str).str.strip()
        df["category"] = df["category"].fillna("General").astype(str).str.strip()
        df["seat_type"] = df["seat_type"].fillna("Government").astype(str).str.strip()
        df["quota"] = df["quota"].fillna("").astype(str).str.strip()

        # Numeric columns
        df["opening_rank"] = pd.to_numeric(df["opening_rank"], errors="coerce").fillna(0).astype(int)
        df["closing_rank"] = pd.to_numeric(df["closing_rank"], errors="coerce").fillna(0).astype(int)
        df["year"] = pd.to_numeric(df["year"], errors="coerce").fillna(2024).astype(int)

        # Remove rows with invalid closing rank
        df = df[df["closing_rank"] > 0].copy()

        return df

    # ── Core Prediction ───────────────────────────────────────────────

    def predict(
        self,
        rank: int,
        category: str = "General",
        exam: str = "CEE",
        branch: Optional[str] = None,
        year: Optional[int] = None,
        quota: Optional[str] = None,
        limit: int = 10,
    ) -> PredictionBundle:
        """
        Run deterministic rank prediction.

        Classification logic:
          - SAFE:      user_rank <= closing_rank * 0.85  (rank is well within cutoff)
          - TARGET:    closing_rank * 0.85 < user_rank <= closing_rank * 1.10
          - AMBITIOUS: closing_rank * 1.10 < user_rank <= closing_rank * 1.40

        Returns a PredictionBundle with safe/target/ambitious options
        and the evidence rows used.
        """
        if not self._data_loaded:
            return PredictionBundle(
                assumptions=["Data not loaded"],
                query_params={"rank": rank, "category": category, "exam": exam},
            )

        df = self._get_exam_df(exam)
        if df.empty:
            return PredictionBundle(
                assumptions=[f"No data available for {exam}"],
                query_params={"rank": rank, "category": category, "exam": exam},
            )

        # ── Filter: category ──────────────────────────────────────
        filtered = df[df["category"].str.upper() == category.upper()].copy()

        # If no results for the exact category, note it and use all data
        assumptions = []
        if filtered.empty:
            assumptions.append(f"No data for category '{category}'; showing General category results")
            filtered = df[df["category"].str.upper() == "GENERAL"].copy()

        # ── Filter: branch (optional) ──────────────────────────────
        if branch:
            branch_filtered = filtered[
                filtered["branch"].str.lower().str.contains(branch.lower(), na=False)
            ]
            if not branch_filtered.empty:
                filtered = branch_filtered
            else:
                assumptions.append(f"No exact match for branch '{branch}'; showing all branches")

        # ── Filter: year (use latest year if not specified) ────────
        if year:
            year_filtered = filtered[filtered["year"] == year]
            if not year_filtered.empty:
                filtered = year_filtered
            else:
                assumptions.append(f"No data for year {year}; using latest available")

        # Use the latest round per college+branch combination
        # (keep the row with the highest round or closing_rank per group)
        if not filtered.empty:
            latest_year = filtered["year"].max()
            filtered = filtered[filtered["year"] == latest_year].copy()
            # Deduplicate: keep the row with the highest closing rank per college+branch
            filtered = (
                filtered
                .sort_values("closing_rank", ascending=False)
                .drop_duplicates(subset=["college_name", "branch"], keep="first")
            )

        # ── Filter: quota (JEE-specific) ───────────────────────────
        if quota and "quota" in filtered.columns:
            quota_filtered = filtered[
                filtered["quota"].str.upper().str.contains(quota.upper(), na=False)
            ]
            if not quota_filtered.empty:
                filtered = quota_filtered

        # ── Classify into bands ────────────────────────────────────
        safe: List[PredictionResult] = []
        target: List[PredictionResult] = []
        ambitious: List[PredictionResult] = []

        for _, row in filtered.iterrows():
            closing = int(row["closing_rank"])
            opening = int(row["opening_rank"])

            result = PredictionResult(
                college_name=str(row["college_name"]),
                college_code=str(row["college_code"]),
                branch=str(row["branch"]),
                category=str(row["category"]),
                opening_rank=opening,
                closing_rank=closing,
                year=int(row["year"]),
                seat_type=str(row["seat_type"]),
                exam=str(row.get("exam", exam)),
                quota=str(row.get("quota", "")) or None,
            )

            # Calculate match percentage and classify
            band, match_pct, reason = self._classify_rank(rank, opening, closing)
            result.band = band
            result.match_percentage = match_pct
            result.reason = reason

            if band == "safe":
                safe.append(result)
            elif band == "target":
                target.append(result)
            elif band == "ambitious":
                ambitious.append(result)

        # Sort each band by match percentage (best first)
        safe.sort(key=lambda r: r.match_percentage, reverse=True)
        target.sort(key=lambda r: r.match_percentage, reverse=True)
        ambitious.sort(key=lambda r: r.match_percentage, reverse=True)

        # Apply limits
        safe = safe[:limit]
        target = target[:limit]
        ambitious = ambitious[:limit]

        total_evidence = len(safe) + len(target) + len(ambitious)

        return PredictionBundle(
            safe_options=safe,
            target_options=target,
            ambitious_options=ambitious,
            evidence_rows_used=total_evidence,
            assumptions=assumptions,
            query_params={
                "rank": rank,
                "category": category,
                "exam": exam,
                "branch": branch,
                "year": year or (filtered["year"].max() if not filtered.empty else None),
            },
        )

    def get_colleges_list(
        self,
        rank: int,
        category: str = "General",
        exam: str = "CEE",
        branch: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Deterministic endpoint for GET /api/colleges.
        Returns a flat list of matching colleges sorted by match percentage.
        """
        bundle = self.predict(rank=rank, category=category, exam=exam, branch=branch, limit=limit)
        
        all_options = []
        for opt in bundle.safe_options + bundle.target_options + bundle.ambitious_options:
            all_options.append({
                "college_name": opt.college_name,
                "college_code": opt.college_code,
                "branch": opt.branch,
                "category": opt.category,
                "opening_rank": opt.opening_rank,
                "closing_rank": opt.closing_rank,
                "year": opt.year,
                "match_percentage": opt.match_percentage,
                "seat_type": opt.seat_type,
                "band": opt.band,
            })

        # Sort by match percentage descending
        all_options.sort(key=lambda x: x["match_percentage"], reverse=True)
        return all_options[:limit]

    def get_available_colleges(self, exam: str = "CEE") -> List[str]:
        """Return a list of all unique college names for the given exam."""
        df = self._get_exam_df(exam)
        if df.empty:
            return []
        return sorted(df["college_name"].unique().tolist())

    def get_available_branches(self, exam: str = "CEE", college_name: Optional[str] = None) -> List[str]:
        """Return all available branches, optionally filtered by college."""
        df = self._get_exam_df(exam)
        if df.empty:
            return []
        if college_name:
            df = df[df["college_name"].str.upper() == college_name.upper()]
        return sorted(df["branch"].unique().tolist())

    def get_available_categories(self, exam: str = "CEE") -> List[str]:
        """Return all available categories for the given exam."""
        df = self._get_exam_df(exam)
        if df.empty:
            return []
        return sorted(df["category"].unique().tolist())

    def get_stats(self) -> Dict[str, Any]:
        """Return data statistics for health checks."""
        return {
            "cee_records": len(self._cee_df) if self._cee_df is not None else 0,
            "jee_records": len(self._jee_df) if self._jee_df is not None else 0,
            "cee_colleges": self._cee_df["college_name"].nunique() if self._cee_df is not None and not self._cee_df.empty else 0,
            "jee_colleges": self._jee_df["college_name"].nunique() if self._jee_df is not None and not self._jee_df.empty else 0,
            "cee_years": sorted(self._cee_df["year"].unique().tolist()) if self._cee_df is not None and not self._cee_df.empty else [],
            "jee_years": sorted(self._jee_df["year"].unique().tolist()) if self._jee_df is not None and not self._jee_df.empty else [],
            "data_loaded": self._data_loaded,
        }

    # ── Private Helpers ───────────────────────────────────────────────

    def _get_exam_df(self, exam: str) -> pd.DataFrame:
        """Return the DataFrame for the given exam type."""
        exam_upper = exam.upper()
        if exam_upper == "CEE":
            return self._cee_df if self._cee_df is not None else pd.DataFrame()
        elif exam_upper in ("JEE", "JEE MAINS", "JEE ADVANCED"):
            return self._jee_df if self._jee_df is not None else pd.DataFrame()
        else:
            logger.warning("Unknown exam type: %s, defaulting to CEE", exam)
            return self._cee_df if self._cee_df is not None else pd.DataFrame()

    def _classify_rank(
        self, user_rank: int, opening_rank: int, closing_rank: int
    ) -> Tuple[str, float, str]:
        """
        Classify a user's rank against a college+branch cutoff.

        Returns (band, match_percentage, reason).

        Band logic:
          - SAFE:      user_rank <= closing_rank * 0.85
                       (comfortably within cutoff — high confidence)
          - TARGET:    closing_rank * 0.85 < user_rank <= closing_rank * 1.10
                       (near the cutoff — moderate confidence)
          - AMBITIOUS: closing_rank * 1.10 < user_rank <= closing_rank * 1.40
                       (above cutoff but within reach — lower confidence)
          - EXCLUDED:  user_rank > closing_rank * 1.40
                       (too far above cutoff — not included in results)
        """
        if closing_rank <= 0:
            return ("ambitious", 0.0, "Invalid closing rank")

        safe_threshold = closing_rank * 0.85
        target_threshold = closing_rank * 1.10
        ambitious_threshold = closing_rank * 1.40

        if user_rank <= safe_threshold:
            # Well within cutoff
            match_pct = 95.0 + (5.0 * max(0, 1 - user_rank / max(closing_rank, 1)))
            match_pct = min(100.0, match_pct)
            return ("safe", round(match_pct, 1), f"Rank {user_rank} is well within closing rank {closing_rank}")

        elif user_rank <= closing_rank:
            # Within cutoff but close
            ratio = user_rank / closing_rank
            match_pct = 95.0 - (ratio - 0.85) * (15.0 / 0.15)  # 95% to 80%
            match_pct = max(80.0, min(95.0, match_pct))
            return ("safe", round(match_pct, 1), f"Rank {user_rank} is within closing rank {closing_rank}")

        elif user_rank <= target_threshold:
            # Slightly above cutoff — target zone
            excess_ratio = (user_rank - closing_rank) / (closing_rank * 0.10)
            match_pct = 75.0 - excess_ratio * 15.0  # 75% down to 60%
            match_pct = max(60.0, min(75.0, match_pct))
            return ("target", round(match_pct, 1), f"Rank {user_rank} is near closing rank {closing_rank} — competitive chance")

        elif user_rank <= ambitious_threshold:
            # Well above cutoff — ambitious
            excess_ratio = (user_rank - target_threshold) / (closing_rank * 0.30)
            match_pct = 55.0 - excess_ratio * 20.0  # 55% down to 35%
            match_pct = max(35.0, min(55.0, match_pct))
            return ("ambitious", round(match_pct, 1), f"Rank {user_rank} is above closing rank {closing_rank} — ambitious but possible")

        else:
            # Too far — excluded from results
            return ("excluded", 0.0, "")


# ── Module-level singleton ────────────────────────────────────────────
cutoff_engine = CutoffEngine()
