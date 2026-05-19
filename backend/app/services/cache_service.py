"""
RankRoute V2 — Cache Service

In-memory cache with TTL support for reducing repeated LLM calls
and redundant cutoff queries. Caches:
  - Parsed intent objects for common queries
  - Prediction results for repeated rank/category/branch combos
  - College web summaries
  - Final answer drafts for identical normalized queries

From V2 plan: "Caching is essential because repeated rank/category queries
and repeated college-information queries are common."
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger("rankroute.services.cache")


@dataclass
class CacheEntry:
    """A single cached item with TTL tracking."""
    value: Any
    created_at: float
    ttl_seconds: float
    hits: int = 0

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_seconds


class CacheService:
    """Thread-safe in-memory cache with TTL and hit tracking.

    Separate namespaces keep different data types isolated:
      - "intent"     — parsed RequestFrame objects
      - "prediction"  — PredictionAgentOutput results
      - "web_summary" — college web knowledge summaries
      - "answer"      — final synthesized answer contexts
    """

    # Default TTL per namespace (seconds)
    DEFAULT_TTLS = {
        "intent": 300,          # 5 min — query parsing is stable
        "prediction": 600,      # 10 min — cutoff data rarely changes
        "web_summary": 1800,    # 30 min — web content is semi-static
        "answer": 120,          # 2 min — answers depend on history context
    }

    def __init__(self, max_entries_per_ns: int = 500):
        self._stores: Dict[str, Dict[str, CacheEntry]] = {}
        self._max_entries = max_entries_per_ns
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}

    def _get_store(self, namespace: str) -> Dict[str, CacheEntry]:
        if namespace not in self._stores:
            self._stores[namespace] = {}
        return self._stores[namespace]

    @staticmethod
    def make_key(*parts) -> str:
        """Build a deterministic cache key from parts."""
        raw = ":".join(str(p).lower().strip() for p in parts if p is not None)
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    def get(self, namespace: str, key: str) -> Optional[Any]:
        """Retrieve a cached value, returning None if missing or expired."""
        store = self._get_store(namespace)
        entry = store.get(key)

        if entry is None:
            self._stats["misses"] += 1
            return None

        if entry.is_expired:
            del store[key]
            self._stats["misses"] += 1
            return None

        entry.hits += 1
        self._stats["hits"] += 1
        return entry.value

    def set(self, namespace: str, key: str, value: Any, ttl: Optional[float] = None):
        """Store a value with optional TTL override."""
        store = self._get_store(namespace)
        ttl = ttl or self.DEFAULT_TTLS.get(namespace, 300)

        # Evict expired entries if store is full
        if len(store) >= self._max_entries:
            self._evict_expired(store)

        # If still full, evict oldest
        if len(store) >= self._max_entries:
            oldest_key = min(store, key=lambda k: store[k].created_at)
            del store[oldest_key]
            self._stats["evictions"] += 1

        store[key] = CacheEntry(
            value=value,
            created_at=time.time(),
            ttl_seconds=ttl,
        )

    def invalidate(self, namespace: str, key: Optional[str] = None):
        """Invalidate a specific key or an entire namespace."""
        if key:
            store = self._get_store(namespace)
            store.pop(key, None)
        else:
            self._stores.pop(namespace, None)

    def clear(self):
        """Clear all caches."""
        self._stores.clear()
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}

    def get_stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0.0
        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "evictions": self._stats["evictions"],
            "hit_rate_pct": round(hit_rate, 1),
            "namespaces": {
                ns: len(store) for ns, store in self._stores.items()
            },
            "total_entries": sum(len(s) for s in self._stores.values()),
        }

    def _evict_expired(self, store: Dict[str, CacheEntry]):
        """Remove expired entries from a store."""
        expired = [k for k, v in store.items() if v.is_expired]
        for k in expired:
            del store[k]
            self._stats["evictions"] += 1


# Singleton
cache_service = CacheService()
