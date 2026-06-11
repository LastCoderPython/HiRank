"""
RankRoute V2 — Content Validator (Phase 18)

Validates scraped page content BEFORE embedding to prevent garbage,
error pages, and thin content from entering the vector store.

Architecture:
  Called after clean_page() and before chunk_text() in _async_ingestion.
  Fail-open on exceptions — ingestion never blocks if validator crashes.
  Conservative thresholds initially — tunable via module-level constants.

Checks:
  - validate_title:      Reject empty, branded error, or very short titles
  - validate_symbol_ratio: Reject garbled text (encoding corruption)
  - validate_type_specific: Downgrade fee/placement/seat pages lacking numbers
  - thin content:         Reject general pages under MIN_GENERAL_WORDS
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

logger = logging.getLogger("rankroute.ingestion.validator")

# ── Tunable thresholds (conservative initial values) ──────────────────
MIN_TITLE_LENGTH = 3
MAX_SYMBOL_RATIO = 0.40
MIN_GENERAL_WORDS = 30
MIN_ADMISSION_NOTICE_WORDS = 50

# Title patterns that indicate a non-content or error page
BAD_TITLE_PATTERNS = re.compile(
    r"(?i)"
    r"404|not\s*found|error|page\s*not\s*found|"
    r"access\s*denied|forbidden|under\s*construction|"
    r"coming\s*soon|redirecting|site\s*down|maintenance|"
    r"website\s*expired|domain\s*expired|"
    r"server\s*error|internal\s*server\s*error|"
    r"no\s*data|empty|blank\s*page"
)


@dataclass
class ValidationResult:
    """Result of validating a single page before embedding."""
    is_valid: bool = True
    reason: str = "passed"
    rejected_by: str = ""
    downgrade_to: Optional[str] = None
    checks: Dict[str, bool] = field(default_factory=dict)


def validate_title(title: str, url: str) -> Tuple[bool, Optional[str]]:
    """Check page title for error indicators or missing data.

    Returns (is_valid, rejection_reason).
    is_valid=True means the title is acceptable.
    """
    stripped = title.strip()

    if not stripped:
        return (False, "empty title")

    if len(stripped) < MIN_TITLE_LENGTH:
        return (False, f"title too short ({len(stripped)} chars)")

    if BAD_TITLE_PATTERNS.search(stripped):
        return (False, f"title indicates error page: '{stripped[:60]}'")

    return (True, None)


def validate_symbol_ratio(text: str) -> Tuple[bool, Optional[str]]:
    """Detect garbled text from encoding corruption.

    Counts alphanumeric vs total characters. If the ratio of
    non-alphanumeric characters exceeds MAX_SYMBOL_RATIO, the text
    is likely garbled or a parsing error.
    """
    if not text:
        return (False, "empty text")

    total = len(text)
    alnum = sum(1 for c in text if c.isalnum())
    if total == 0:
        return (False, "empty text")

    ratio = 1.0 - (alnum / total)
    if ratio > MAX_SYMBOL_RATIO:
        return (False, f"symbol ratio too high ({ratio:.2f} > {MAX_SYMBOL_RATIO})")

    return (True, None)


def validate_type_specific(
    page_type: str,
    text: str,
    word_count: int,
) -> Tuple[bool, Optional[str]]:
    """Check page content against its classified type.

    Returns (is_valid, downgrade_to).
    - is_valid=False means the page should be rejected.
    - downgrade_to=None means the page passes without change.
    - downgrade_to="general" means the page passes but with reduced trust.
    """
    checked_type = page_type.lower()

    if checked_type in ("about", "facilities", "branch_info", "hostel", "notice", "notices", "general"):
        return (True, None)

    if checked_type in ("fees", "fee_structure"):
        if not re.search(r"\d", text):
            return (True, "general")
        return (True, None)

    if checked_type in ("placement", "placements", "placement_stats"):
        if not re.search(r"[%]|[Ll][Pp][Aa]|[Ll]akh|\d{3,}", text):
            return (True, "general")
        return (True, None)

    if checked_type in ("seat_matrix", "intake"):
        if not re.search(r"\d", text):
            return (True, "general")
        return (True, None)

    if checked_type in ("admission_notice",):
        if word_count < MIN_ADMISSION_NOTICE_WORDS:
            return (True, "notice")
        return (True, None)

    return (True, None)


def validate_page(
    cleaned_page,
    raw_html: str,
    url: str,
) -> ValidationResult:
    """Run all validation checks on a cleaned page.

    Order: title → symbol ratio → type-specific → thin content.
    Returns early on first rejection.
    """
    from app.ingestion.page_cleaner import CleanedPage
    assert isinstance(cleaned_page, CleanedPage), "Expected CleanedPage"

    checks: Dict[str, bool] = {}

    # ── 1. Title validation ──────────────────────────────────────────
    title_valid, title_reason = validate_title(cleaned_page.title, url)
    checks["title"] = title_valid
    if not title_valid:
        return ValidationResult(
            is_valid=False,
            reason=f"title: {title_reason}",
            rejected_by="title",
            checks=checks,
        )

    # ── 2. Symbol ratio ─────────────────────────────────────────────
    symbol_valid, symbol_reason = validate_symbol_ratio(cleaned_page.text)
    checks["symbol_ratio"] = symbol_valid
    if not symbol_valid:
        return ValidationResult(
            is_valid=False,
            reason=f"symbol_ratio: {symbol_reason}",
            rejected_by="symbol_ratio",
            checks=checks,
        )

    # ── 3. Type-specific content check ───────────────────────────────
    type_valid, downgrade_to = validate_type_specific(
        cleaned_page.page_type, cleaned_page.text, cleaned_page.word_count,
    )
    checks["type_specific"] = type_valid
    if type_valid and downgrade_to:
        # Downgrade (pass but with reduced page_type)
        return ValidationResult(
            is_valid=True,
            reason=f"downgraded from {cleaned_page.page_type} to {downgrade_to}",
            downgrade_to=downgrade_to,
            checks=checks,
        )
    if not type_valid:
        return ValidationResult(
            is_valid=False,
            reason=f"type_specific: {cleaned_page.page_type} content check failed",
            rejected_by="type_specific",
            checks=checks,
        )

    # ── 4. Thin content gate ─────────────────────────────────────────
    thin_valid = True
    if cleaned_page.page_type == "general" and cleaned_page.word_count < MIN_GENERAL_WORDS:
        thin_valid = False
        checks["thin_content"] = False
        return ValidationResult(
            is_valid=False,
            reason=f"general page too thin ({cleaned_page.word_count} words, min {MIN_GENERAL_WORDS})",
            rejected_by="thin_content",
            checks=checks,
        )
    checks["thin_content"] = True

    return ValidationResult(
        is_valid=True,
        reason="passed",
        checks=checks,
    )
