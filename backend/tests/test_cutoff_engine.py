"""Tests for CutoffEngine reload and rollback behavior."""

from __future__ import annotations

import pytest
from app.retrieval.cutoff_engine import cutoff_engine


class TestCutoffEngineReload:
    def test_reload_returns_stats(self):
        stats = cutoff_engine.reload()
        assert "cee_rows" in stats
        assert "jee_rows" in stats
        assert "status" in stats
        assert stats["status"] == "ok"
        assert isinstance(stats["cee_rows"], int)
        assert isinstance(stats["jee_rows"], int)

    def test_get_stats_before_and_after_reload(self):
        before = cutoff_engine.get_stats()
        cutoff_engine.reload()
        after = cutoff_engine.get_stats()
        assert before["data_loaded"] == after["data_loaded"]
        assert before["cee_records"] == after["cee_records"]
        assert before["jee_records"] == after["jee_records"]

    def test_engine_still_predicts_after_reload(self):
        cutoff_engine.reload()
        result = cutoff_engine.predict(rank=5000, exam="CEE")
        assert hasattr(result, "safe_options")
        assert hasattr(result, "target_options")
        assert hasattr(result, "ambitious_options")
        assert result.evidence_rows_used >= 0

    def test_reload_with_jee(self):
        stats = cutoff_engine.reload()
        cutoff_engine.predict(rank=1000, exam="JEE")

    def test_rollback_on_reload_failure(self):
        old_stats = cutoff_engine.get_stats()
        old_cee = old_stats["cee_records"]
        old_jee = old_stats["jee_records"]

        with pytest.raises(RuntimeError, match="Reload failed"):
            import pandas as pd
            original_load = cutoff_engine.predict
            def broken_load(*args, **kwargs):
                raise ValueError("Simulated corrupt CSV")
            cutoff_engine.predict = broken_load
            cutoff_engine.reload()

        cutoff_engine.predict = original_load
        post_crash = cutoff_engine.get_stats()
        assert post_crash["cee_records"] == old_cee
        assert post_crash["jee_records"] == old_jee
        assert post_crash["data_loaded"] == old_stats["data_loaded"]


class TestCutoffEnginePrediction:
    def test_predict_returns_bundle(self):
        result = cutoff_engine.predict(rank=5000, category="General", exam="CEE")
        assert result.query_params["rank"] == 5000
        assert result.query_params["category"] == "General"
        assert result.query_params["exam"] == "CEE"

    def test_predict_with_branch_filter(self):
        result = cutoff_engine.predict(rank=5000, exam="CEE", branch="CSE")
        assert result is not None

    def test_predict_unknown_exam_defaults_to_cee(self):
        result = cutoff_engine.predict(rank=5000, exam="UNKNOWN")
        assert result is not None
