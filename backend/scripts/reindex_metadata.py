"""
RankRoute — Chroma Metadata Reindex Script

Audits and normalizes the college_web_docs Chroma collection metadata.
Run after ingestion or yearly data updates to ensure metadata consistency.

Usage:
    python -m scripts.reindex_metadata [--dry-run] [--purge-invalid]

Actions:
  1. Inspect all metadata in the college_web_docs collection
  2. Normalize college_name to uppercase acronyms
  3. Report page_type values outside the controlled vocabulary
  4. Optionally purge entries with validation_status != "passed"
"""

import argparse
import logging
import sys
from typing import Dict, Any, List
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("reindex_metadata")

CONTROLLED_PAGE_TYPES = frozenset({
    "about", "overview", "general",
    "fees", "fee_structure",
    "placement", "placements", "placement_stats",
    "hostel", "accommodation", "campus_life",
    "facilities", "infrastructure", "campus",
    "notice", "admission_notice", "update", "announcement",
    "branch_info", "programs", "courses",
    "seat_matrix", "intake",
})


def audit_collection() -> Dict[str, Any]:
    """Inspect all metadata in college_web_docs and return a report."""
    from app.core.chroma_client import chroma_client

    info = chroma_client.inspect_metadata("college_web_docs")
    logger.info("Total documents: %d", info["total_docs"])
    logger.info("Unique colleges: %s", info["unique_colleges"])
    logger.info("Unique page types: %s", info["unique_page_types"])
    logger.info("Validation statuses: %s", info["validation_statuses"])
    logger.info("Domains: %s", info["domains"])

    # Check for null college_name
    if info["null_college_name"] > 0:
        logger.warning("Entries with null college_name: %d", info["null_college_name"])

    # Check for null page_type
    if info["null_page_type"] > 0:
        logger.warning("Entries with null page_type: %d", info["null_page_type"])

    # Check for uncontrolled page types
    uncontrolled = {pt for pt in info["unique_page_types"] if pt not in CONTROLLED_PAGE_TYPES}
    if uncontrolled:
        logger.warning("Uncontrolled page_types: %s", sorted(uncontrolled))

    return info


def normalize_college_names(collection, dry_run: bool = True) -> int:
    """Normalize college_name metadata to uppercase acronyms."""
    records = collection.get(include=["metadatas"])
    metas = records["metadatas"] or []
    ids = records["ids"] or []
    normalized_count = 0

    for i, meta in enumerate(metas):
        raw = (meta.get("college_name") or "").strip()
        # Map known full names to acronyms
        name_map = {
            "assam engineering college": "AEC",
            "jorhat engineering college": "JEC",
            "dibrugarh university": "DU",
            "gauhati university": "GU",
            "tezpur university": "TU",
            "nagaland university": "NU",
            "assam university": "AU",
            "dibrugarh engineering college": "DEC",
            "dhemaji engineering college": "DHEC",
            "barak valley engineering college": "BVEC",
            "bineswar brahma engineering college": "BBEC",
            "nowgong girls engineering college": "NGEC",
            "central institute of technology": "CIT",
            "national institute of technology, silchar": "NITS",
            "nits": "NITS",
        }
        mapped = name_map.get(raw.lower(), "")
        if mapped and mapped != raw.upper():
            normalized_count += 1
            if not dry_run:
                collection.update(ids=[ids[i]], metadatas=[{**meta, "college_name": mapped}])

    logger.info("Colleges needing normalization: %d (dry_run=%s)", normalized_count, dry_run)
    return normalized_count


def purge_invalid_validation_status(collection, dry_run: bool = True) -> int:
    """Remove entries with validation_status != 'passed'."""
    records = collection.get(include=["metadatas"])
    metas = records["metadatas"] or []
    ids = records["ids"] or []
    to_purge = []

    for i, meta in enumerate(metas):
        vs = meta.get("validation_status", "passed")
        if vs != "passed":
            to_purge.append(ids[i])

    if not dry_run and to_purge:
        collection.delete(ids=to_purge)
        logger.info("Purged %d entries with invalid validation_status", len(to_purge))
    else:
        logger.info("Entries to purge: %d (dry_run=%s)", len(to_purge), dry_run)

    return len(to_purge)


def main():
    parser = argparse.ArgumentParser(description="Reindex and normalize Chroma metadata")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Preview changes without applying them (default: True)")
    parser.add_argument("--no-dry-run", action="store_false", dest="dry_run",
                        help="Apply changes")
    parser.add_argument("--purge-invalid", action="store_true", default=False,
                        help="Purge entries with validation_status != 'passed'")
    args = parser.parse_args()

    logger.info("Starting Chroma metadata reindex (dry_run=%s)", args.dry_run)

    from app.core.chroma_client import chroma_client
    collection = chroma_client.get_collection("college_web_docs")

    audit_collection()
    normalize_college_names(collection, dry_run=args.dry_run)

    if args.purge_invalid:
        purge_invalid_validation_status(collection, dry_run=args.dry_run)

    logger.info("Reindex complete.")


if __name__ == "__main__":
    main()
