"""Tests for admin CSV validation and backup logic."""

from __future__ import annotations

import pytest
from app.api.admin import (
    _normalize_cutoff_columns,
    _validate_cutoff_csv,
    _validate_college_info_csv,
    CUTOFF_RENAME_MAP,
    CEE_REQUIRED_COLS,
    JEE_REQUIRED_COLS,
    COLLEGE_DATA_COLUMNS,
    VALID_COLLEGE_DATA_TYPES,
    _save_with_backup,
    _check_csv_mime,
)
from fastapi import HTTPException
from pathlib import Path
import tempfile
import os


VALID_CEE_CSV = """college_name,college_code,branch,category,opening_rank,closing_rank,year,seat_type
JEC,101,CSE,General,100,500,2024,Government
AEC,102,ECE,OBC,200,600,2024,Government"""

VALID_JEE_CSV = """college_name,college_code,branch,category,opening_rank,closing_rank,year,seat_type,quota
NITS,201,CSE,General,50,300,2024,Government,Home State
JEC,202,ECE,OBC,100,400,2024,Government,All India"""

MISSING_COL_CSV = """college_name,branch,category,opening_rank,closing_rank,year,seat_type
JEC,CSE,General,100,500,2024,Government"""

INVALID_RANK_CSV = """college_name,college_code,branch,category,opening_rank,closing_rank,year,seat_type
JEC,101,CSE,General,abc,xyz,2024,Government"""

INVALID_YEAR_CSV = """college_name,college_code,branch,category,opening_rank,closing_rank,year,seat_type
JEC,101,CSE,General,100,500,1999,Government"""

NEGATIVE_CL_CSV = """college_name,college_code,branch,category,opening_rank,closing_rank,year,seat_type
JEC,101,CSE,General,100,0,2024,Government"""


class TestNormalizeCutoffColumns:
    def test_standard_columns_passthrough(self):
        row = {"college_name": "JEC", "branch": "CSE"}
        result = _normalize_cutoff_columns(row)
        assert result["college_name"] == "JEC"
        assert result["branch"] == "CSE"

    def test_alias_columns_get_mapped(self):
        row = {"college": "JEC", "branch_name": "CSE", "op_rank": "100", "cl_rank": "500"}
        result = _normalize_cutoff_columns(row)
        assert result["college_name"] == "JEC"
        assert result["branch"] == "CSE"
        assert result["opening_rank"] == "100"
        assert result["closing_rank"] == "500"

    def test_case_insensitive(self):
        row = {"COLLEGE": "JEC", "BRANCH_NAME": "CSE"}
        result = _normalize_cutoff_columns(row)
        assert result["college_name"] == "JEC"
        assert result["branch"] == "CSE"

    def test_unknown_column_passthrough(self):
        row = {"custom_col": "value"}
        result = _normalize_cutoff_columns(row)
        assert result["custom_col"] == "value"


class TestValidateCutoffCsv:
    def test_valid_cee_passes(self):
        result = _validate_cutoff_csv(VALID_CEE_CSV, "CEE")
        assert result["valid"]
        assert result["rows"] == 2
        assert len(result["errors"]) == 0

    def test_valid_jee_passes(self):
        result = _validate_cutoff_csv(VALID_JEE_CSV, "JEE")
        assert result["valid"]
        assert result["rows"] == 2

    def test_jee_missing_quota_column_fails(self):
        result = _validate_cutoff_csv(VALID_CEE_CSV, "JEE")
        assert not result["valid"]
        assert any("quota" in e for e in result["errors"])

    def test_missing_college_code_column(self):
        result = _validate_cutoff_csv(MISSING_COL_CSV, "CEE")
        assert not result["valid"]
        assert any("college_code" in e for e in result["errors"])

    def test_invalid_rank_values(self):
        result = _validate_cutoff_csv(INVALID_RANK_CSV, "CEE")
        assert not result["valid"]
        errors_str = " ".join(result["errors"]).lower()
        assert "opening_rank" in errors_str
        assert "closing_rank" in errors_str

    def test_year_out_of_range(self):
        result = _validate_cutoff_csv(INVALID_YEAR_CSV, "CEE")
        assert not result["valid"]
        assert any("year" in e for e in result["errors"])

    def test_preview_limited_to_5_rows(self):
        many_rows = "\n".join([VALID_CEE_CSV.split("\n")[0]] + [
            f"JEC,{i},CSE,General,{100+i},{500+i},2024,Government" for i in range(10)
        ])
        result = _validate_cutoff_csv(many_rows, "CEE")
        assert result["rows"] == 10
        assert len(result["preview"]) <= 5

    def test_negative_opening_rank_fails(self):
        csv = """college_name,college_code,branch,category,opening_rank,closing_rank,year,seat_type
JEC,101,CSE,General,-1,500,2024,Government"""
        result = _validate_cutoff_csv(csv, "CEE")
        assert not result["valid"]

    def test_closing_rank_zero_fails(self):
        result = _validate_cutoff_csv(NEGATIVE_CL_CSV, "CEE")
        assert not result["valid"]


class TestValidateCollegeInfoCsv:
    def test_invalid_data_type_rejected(self):
        assert "invalid_type" not in VALID_COLLEGE_DATA_TYPES

    def test_fee_structure_columns_validated(self):
        csv = """college_name,college_code,program,tuition_fee_per_sem,hostel_fee_per_sem,total_per_sem,total_first_year
JEC,101,B.Tech,50000,10000,60000,120000"""
        result = _validate_college_info_csv(csv, "fee_structure")
        assert result["valid"]
        assert result["rows"] == 1

    def test_fee_structure_missing_column(self):
        csv = """college_name,college_code,program
JEC,101,B.Tech"""
        result = _validate_college_info_csv(csv, "fee_structure")
        assert not result["valid"]

    def test_placement_stats_valid(self):
        csv = """college_name,college_code,branch,avg_package_lpa,highest_package_lpa,placement_percentage
JEC,101,CSE,12.5,25,95"""
        result = _validate_college_info_csv(csv, "placement_stats")
        assert result["valid"]

    def test_college_basic_info_valid(self):
        csv = """college_name,college_code,location,district,state,type,affiliation,website
JEC,101,Guwahati,Kamrup,Assam,Government,ASTU,https://jec.ac.in"""
        result = _validate_college_info_csv(csv, "colleges_basic_info")
        assert result["valid"]


class TestBackupSave:
    def test_save_with_backup_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            active = Path(tmp) / "test.csv"
            result = _save_with_backup(str(active), "a,b\n1,2", "admin1")
            assert active.exists()
            assert active.read_text() == "a,b\n1,2"
            assert result["backup_id"] is not None

    def test_save_with_backup_creates_backup_of_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            active = Path(tmp) / "test.csv"
            active.write_text("old,data\n1,2")
            result = _save_with_backup(str(active), "new,data\n3,4", "admin1")
            assert active.read_text() == "new,data\n3,4"
            assert result["backup_path"] is not None
            backup_file = Path(result["backup_path"])
            assert backup_file.exists()
            assert "old,data" in backup_file.read_text()


class TestCheckCsvMime:
    def test_allowed_mime_types(self):
        for mime in ["text/csv", "text/x-csv", "application/csv", "application/x-csv"]:
            _check_csv_mime(mime)

    def test_rejected_mime_types(self):
        for mime in ["image/png", "text/plain", "application/vnd.ms-excel", "application/octet-stream"]:
            with pytest.raises(HTTPException):
                _check_csv_mime(mime)

    def test_none_mime_skips_check(self):
        _check_csv_mime(None)
