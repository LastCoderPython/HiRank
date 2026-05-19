"""
RankRoute V2 — Structured Prediction Agent

A mostly-deterministic specialist agent that queries the cutoff engine
(structured truth) for rank-based admission prediction.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.retrieval.cutoff_engine import cutoff_engine, PredictionBundle
from app.orchestration.types import (
    CutoffEvidenceRow,
    PredictionAgentOutput,
    PredictionBand,
    PredictionOption,
    RequestFrame,
)

logger = logging.getLogger("rankroute.agents.structured_prediction")


class StructuredPredictionAgent:
    """
    Specialist agent for deterministic admission prediction.

    Responsibilities:
      - Apply rank/category/branch filtering via the CutoffEngine.
      - Compute safe / target / ambitious confidence bands.
      - Return evidence rows, assumptions, and structured shortlist.
      - Never invent reasoning — only package deterministic results.
    """

    def __init__(self):
        self.engine = cutoff_engine

    async def run(self, frame: RequestFrame) -> PredictionAgentOutput:
        """Execute a structured prediction given a RequestFrame."""
        if frame.rank is None:
            logger.warning("StructuredPredictionAgent called without rank")
            return PredictionAgentOutput(
                assumptions=["No rank provided — cannot predict"],
                evidence_rows_used=0,
            )

        exam = frame.exam or "CEE"
        category = frame.category or "General"
        branch = frame.branch_preference

        logger.info(
            "Prediction: rank=%d, category=%s, exam=%s, branch=%s",
            frame.rank, category, exam, branch,
        )

        bundle: PredictionBundle = self.engine.predict(
            rank=frame.rank,
            category=category,
            exam=exam,
            branch=branch,
            limit=10,
        )

        safe_options = [self._to_option(r, PredictionBand.SAFE) for r in bundle.safe_options]
        target_options = [self._to_option(r, PredictionBand.TARGET) for r in bundle.target_options]
        ambitious_options = [self._to_option(r, PredictionBand.AMBITIOUS) for r in bundle.ambitious_options]

        return PredictionAgentOutput(
            safe_options=safe_options,
            target_options=target_options,
            ambitious_options=ambitious_options,
            assumptions=bundle.assumptions,
            evidence_rows_used=bundle.evidence_rows_used,
        )

    def _to_option(self, result, band: PredictionBand) -> PredictionOption:
        evidence = CutoffEvidenceRow(
            college_name=result.college_name,
            college_code=result.college_code,
            branch=result.branch,
            category=result.category,
            opening_rank=result.opening_rank,
            closing_rank=result.closing_rank,
            year=result.year,
            seat_type=result.seat_type,
            exam=result.exam,
            quota=result.quota,
            match_percentage=result.match_percentage,
        )
        return PredictionOption(band=band, evidence=evidence, reason=result.reason)


structured_prediction_agent = StructuredPredictionAgent()
