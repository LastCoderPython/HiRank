"""
RankRoute V2 — Prompt & Policy Versioning

Tracks versions of all prompts and policy configurations so that
behavior changes are auditable. Each version is timestamped and
can be retrieved for debugging or rollback.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("rankroute.services.versioning")


@dataclass
class VersionEntry:
    """A single version snapshot of a prompt or policy config."""
    version: str
    content: Any
    created_at: str = ""
    description: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


class VersioningService:
    """Track and audit prompt/policy versions.

    Usage:
        versioning.register("synthesis_prompt", "v1.0", prompt_text, "Initial prompt")
        versioning.register("routing_policy", "v1.0", policy_config, "7 route categories")

        current = versioning.get_current("synthesis_prompt")
        history = versioning.get_history("synthesis_prompt")
    """

    def __init__(self):
        self._registry: Dict[str, List[VersionEntry]] = {}
        self._current: Dict[str, str] = {}
        self._register_defaults()

    def _register_defaults(self):
        """Register the initial versions of all policies and prompts."""

        # Policy versions
        self.register(
            "routing_policy", "v1.0",
            {
                "categories": [
                    "prediction_simple", "descriptive_simple",
                    "mixed_comparison", "recent_update",
                    "ambiguous", "greeting", "off_topic",
                ],
                "rules": "rank/category/branch -> prediction; college-info -> descriptive; mixed -> parallel",
            },
            "Initial 7-category routing policy",
        )

        self.register(
            "source_authority_policy", "v1.0",
            {
                "cutoff_truth": ["rank_prediction", "eligibility", "safe_target_ambitious"],
                "college_web_docs": ["placements", "hostel", "fees", "facilities", "notices"],
                "rule": "web may enrich but never override structured admission truth",
            },
            "Initial source authority rules",
        )

        self.register(
            "budget_policy", "v1.0",
            {
                "tier_0": {"parser_calls": 1, "synthesis_calls": 1},
                "tier_1": {"specialist_calls": 2, "synthesis_calls": 1},
                "tier_2": {"specialist_calls": 3, "synthesis_calls": 1},
                "retrieval_cap": 5,
            },
            "Initial per-tier budget limits",
        )

        self.register(
            "verification_policy", "v1.0",
            {
                "rules": [
                    "no rank claim without cutoff evidence",
                    "no freshness claim without time-qualified source",
                    "no mixed answer if source authority violated",
                    "missing fields -> clarification or scoped output",
                ],
            },
            "Initial verification rules",
        )

        self.register(
            "band_classification", "v1.0",
            {
                "safe": "user_rank <= closing_rank * 0.85",
                "target": "user_rank <= closing_rank * 1.10",
                "ambitious": "user_rank <= closing_rank * 1.40",
            },
            "Deterministic confidence bands for cutoff engine",
        )

        self.register(
            "synthesis_prompt", "v1.0",
            {
                "prediction_instructions": [
                    "Present colleges grouped by confidence band (Safe -> Target -> Ambitious)",
                    "Use exact closing ranks and match percentages from data",
                    "Be encouraging but honest about ambitious options",
                    "Data is from previous year cutoffs; actual cutoffs may vary",
                ],
                "descriptive_instructions": [
                    "Use college information to answer descriptive questions",
                    "Cite specific facts from data. Do not invent details",
                ],
            },
            "Initial synthesis prompt instructions",
        )

    def register(self, name: str, version: str, content: Any, description: str = ""):
        """Register a new version of a prompt or policy."""
        if name not in self._registry:
            self._registry[name] = []

        entry = VersionEntry(
            version=version,
            content=content,
            description=description,
        )
        self._registry[name].append(entry)
        self._current[name] = version
        logger.debug("Registered %s %s: %s", name, version, description)

    def get_current(self, name: str) -> Optional[VersionEntry]:
        """Get the current version of a prompt or policy."""
        history = self._registry.get(name, [])
        current_ver = self._current.get(name)
        if not current_ver or not history:
            return None
        for entry in reversed(history):
            if entry.version == current_ver:
                return entry
        return history[-1] if history else None

    def get_history(self, name: str) -> List[VersionEntry]:
        """Get the full version history of a prompt or policy."""
        return self._registry.get(name, [])

    def get_all_current(self) -> Dict[str, Dict[str, Any]]:
        """Get a summary of all current versions."""
        result = {}
        for name in self._registry:
            current = self.get_current(name)
            if current:
                result[name] = {
                    "version": current.version,
                    "created_at": current.created_at,
                    "description": current.description,
                }
        return result

    def rollback(self, name: str, version: str) -> bool:
        """Rollback a prompt or policy to a previous version."""
        history = self._registry.get(name, [])
        for entry in history:
            if entry.version == version:
                self._current[name] = version
                logger.info("Rolled back %s to %s", name, version)
                return True
        return False


# Singleton
versioning_service = VersioningService()
