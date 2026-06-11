"""Tests for content validator (Phase 18)."""

from __future__ import annotations

from app.ingestion.content_validator import (
    MIN_TITLE_LENGTH,
    MIN_GENERAL_WORDS,
    BAD_TITLE_PATTERNS,
    validate_title,
    validate_symbol_ratio,
    validate_type_specific,
)

PASSABLE_TEXT = " ".join(["word"] * 80)


class TestValidateTitle:
    def test_empty_title_rejected(self):
        valid, reason = validate_title("  ", "http://example.com")
        assert not valid
        assert "empty" in reason

    def test_short_title_rejected(self):
        valid, reason = validate_title("AB", "http://example.com")
        assert not valid
        assert "too short" in reason

    def test_min_length_accepted(self):
        short = "A" * MIN_TITLE_LENGTH
        valid, reason = validate_title(short, "http://example.com")
        assert valid
        assert reason is None

    def test_error_pattern_rejected(self):
        cases = ["404 Not Found", "Error Page", "Page not found", "Access Denied"]
        for title in cases:
            valid, reason = validate_title(title, "http://example.com")
            assert not valid, f"Expected '{title}' to be rejected"
            assert "error page" in reason

    def test_error_pattern_not_triggered(self):
        cases = [
            "Welcome to AEC",
            "JEC Admission 2026",
            "NITS Silchar",
            "Tezpur University",
        ]
        for title in cases:
            valid, reason = validate_title(title, "http://example.com")
            assert valid, f"Expected '{title}' to pass"

    def test_home_title_accepted(self):
        valid, reason = validate_title("Home", "http://example.com")
        assert valid


class TestValidateSymbolRatio:
    def test_empty_text_rejected(self):
        valid, reason = validate_symbol_ratio("")
        assert not valid

    def test_normal_text_passes(self):
        text = "This is a normal English sentence with some numbers 123 and symbols."
        valid, reason = validate_symbol_ratio(text)
        assert valid

    def test_garbled_text_rejected(self):
        text = ">>>===###@@@!!!~~~%%%^^^" + "a"
        valid, reason = validate_symbol_ratio(text)
        assert not valid

    def test_boundary_just_below_threshold(self):
        text = "a" * 60 + "." * 40
        valid, reason = validate_symbol_ratio(text)
        assert valid


class TestValidateTypeSpecific:
    def test_about_page_passes(self):
        valid, downgrade = validate_type_specific("about", PASSABLE_TEXT, 100)
        assert valid
        assert downgrade is None

    def test_fees_with_numbers_passes(self):
        text = "The tuition fee is Rs. 50000 per semester."
        valid, downgrade = validate_type_specific("fees", text, 30)
        assert valid
        assert downgrade is None

    def test_fees_without_numbers_downgraded(self):
        text = "The fee structure is competitive and affordable."
        valid, downgrade = validate_type_specific("fees", text, 30)
        assert valid
        assert downgrade == "general"

    def test_placement_with_stats_passes(self):
        text = "95% placement with average LPA of 12.5 lakhs"
        valid, downgrade = validate_type_specific("placement", text, 30)
        assert valid

    def test_placement_without_stats_downgraded(self):
        text = "Training and placement cell is active."
        valid, downgrade = validate_type_specific("placement", text, 30)
        assert valid
        assert downgrade == "general"

    def test_seat_matrix_with_numbers_passes(self):
        text = "Total seats: 60 for CSE branch."
        valid, downgrade = validate_type_specific("seat_matrix", text, 30)
        assert valid

    def test_seat_matrix_without_numbers_downgraded(self):
        valid, downgrade = validate_type_specific("seat_matrix", "seats available", 30)
        assert valid
        assert downgrade == "general"


class TestConstants:
    def test_min_title_length_is_reasonable(self):
        assert MIN_TITLE_LENGTH == 3

    def test_min_general_words_is_reasonable(self):
        assert MIN_GENERAL_WORDS == 30

    def test_bad_title_patterns_compiles(self):
        assert BAD_TITLE_PATTERNS is not None
