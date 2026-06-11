import pytest
from app.services.email_validator import validate_and_normalize_email


class TestNormalizeEmail:
    def test_lowercases_email(self):
        result, error = validate_and_normalize_email("USER@Example.com")
        assert error is None
        assert result == "user@example.com"

    def test_strips_gmail_dots(self):
        result, error = validate_and_normalize_email("user.name@gmail.com")
        assert error is None
        assert result == "username@gmail.com"

    def test_strips_gmail_plus_alias(self):
        result, error = validate_and_normalize_email("user+spam@gmail.com")
        assert error is None
        assert result == "user@gmail.com"

    def test_handles_gmail_dot_and_plus(self):
        result, error = validate_and_normalize_email("user.name+tag@gmail.com")
        assert error is None
        assert result == "username@gmail.com"

    def test_preserves_non_gmail_dots(self):
        result, error = validate_and_normalize_email("first.last@outlook.com")
        assert error is None
        assert result == "first.last@outlook.com"


class TestRejectDisposable:
    def test_rejects_mailinator(self):
        result, error = validate_and_normalize_email("test@mailinator.com")
        assert error is not None

    def test_rejects_tempmail(self):
        result, error = validate_and_normalize_email("test@tempmail.com")
        assert error is not None

    def test_rejects_guerrillamail(self):
        result, error = validate_and_normalize_email("test@guerrillamail.com")
        assert error is not None

    def test_rejects_yopmail(self):
        result, error = validate_and_normalize_email("test@yopmail.com")
        assert error is not None


class TestInvalidEmails:
    def test_empty_string(self):
        result, error = validate_and_normalize_email("")
        assert error is not None

    def test_no_at_symbol(self):
        result, error = validate_and_normalize_email("notanemail")
        assert error is not None

    def test_no_domain(self):
        result, error = validate_and_normalize_email("user@")
        assert error is not None

    def test_only_whitespace(self):
        result, error = validate_and_normalize_email("  ")
        assert error is not None


class TestValidEmailsPass:
    def test_standard_email_passes(self):
        result, error = validate_and_normalize_email("student@aec.ac.in")
        assert error is None
        assert result == "student@aec.ac.in"

    def test_hotmail_passes(self):
        result, error = validate_and_normalize_email("user@hotmail.com")
        assert error is None
