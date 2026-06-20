"""
RankRoute — Usage Service (Redis-backed Credit Enforcement)

Enforces freemium limits for anonymous and authenticated users:
  - Anonymous: 3 prompts + 1 Tavily search before login wall
  - Authenticated: 5 Tavily searches per calendar month
  - Global: tracks total Tavily usage against monthly quota

All counters live in Redis for cross-worker consistency and crash
safety. Calendar-based key suffixes ({YYYY-MM}) mean monthly
resets happen naturally — no cron job needed.
"""

import logging
from datetime import datetime, timezone
from typing import NamedTuple

import redis

from app.config import settings

logger = logging.getLogger("rankroute.services.usage")


class CreditCheck(NamedTuple):
    """Result of a credit check."""
    allowed: bool
    remaining: int


class UsageService:
    """Redis-backed usage enforcement for freemium gate."""

    def __init__(self):
        self._redis = None

    def _get_redis(self) -> redis.Redis:
        """Lazy-init Redis connection (shared with Celery broker)."""
        if self._redis is None:
            try:
                self._redis = redis.Redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=1,
                )
                self._redis.ping()
                logger.info("UsageService: Redis connected")
            except Exception as e:
                logger.error("UsageService: Redis connection failed: %s", e)
                self._redis = None
        return self._redis

    # ── Atomic Lua Script ─────────────────────────────────────────────

    _CHECK_AND_INCR_SCRIPT = """
    local current = redis.call('INCR', KEYS[1])
    if current == 1 then
        redis.call('EXPIRE', KEYS[1], ARGV[2])
    end
    if current > tonumber(ARGV[1]) then
        redis.call('DECR', KEYS[1])
        return {0, tonumber(ARGV[1])}
    end
    return {1, tonumber(ARGV[1]) - current}
    """

    def _check_and_increment(self, key: str, limit: int, ttl: int) -> CreditCheck:
        """Atomically increment and check limit using a Lua script.

        Prevents race conditions where concurrent INCRs can push the counter
        past the limit before DECR undoes them. The Lua script runs as a
        single atomic operation in Redis.
        """
        r = self._get_redis()
        if r is None:
            return CreditCheck(allowed=True, remaining=limit)

        try:
            result = r.eval(self._CHECK_AND_INCR_SCRIPT, 1, key, limit, ttl)
            allowed = bool(result[0])
            remaining = int(result[1])
            if not allowed:
                logger.info(
                    "Limit hit: key=%s, limit=%d", key[:20], limit,
                )
            return CreditCheck(allowed=allowed, remaining=remaining)
        except Exception as e:
            logger.error("Credit check failed (fail-open): %s", e)
            return CreditCheck(allowed=True, remaining=limit)

    # ── Anonymous Prompt Gate ─────────────────────────────────────────

    def check_and_increment_anon_prompt(self, session_id: str) -> CreditCheck:
        """Check and increment anonymous prompt counter (atomic)."""
        key = f"anon:prompts:{session_id}"
        return self._check_and_increment(key, settings.anon_prompt_limit, 7 * 24 * 3600)

    # ── Anonymous Tavily Gate ─────────────────────────────────────────

    def check_and_increment_anon_tavily(self, session_id: str) -> CreditCheck:
        """Check and increment anonymous Tavily counter (atomic)."""
        key = f"anon:tavily:{session_id}"
        result = self._check_and_increment(key, settings.anon_tavily_limit, 30 * 24 * 3600)
        if result.allowed:
            self._increment_global_counter()
        return result

    # ── Authenticated Tavily Gate ─────────────────────────────────────

    def check_and_increment_auth_tavily(self, user_id: str) -> CreditCheck:
        """Check and increment authenticated user's monthly Tavily counter (atomic).

        Key format: auth:tavily:{user_id}:{YYYY-MM}
        Naturally resets on the 1st of each month because the month
        suffix changes and the old key is never queried again.
        """
        month_key = datetime.now(timezone.utc).strftime("%Y-%m")
        key = f"auth:tavily:{user_id}:{month_key}"
        result = self._check_and_increment(key, settings.auth_tavily_monthly_limit, 35 * 24 * 3600)
        if result.allowed:
            self._increment_global_counter()
        return result

    # ── Global Quota Counter ──────────────────────────────────────────

    def _increment_global_counter(self) -> None:
        """Increment global monthly Tavily counter and check alert thresholds."""
        r = self._get_redis()
        if r is None:
            return

        month_key = datetime.now(timezone.utc).strftime("%Y-%m")
        global_key = f"tavily:global:{month_key}"

        try:
            current = r.incr(global_key)
            if current == 1:
                r.expire(global_key, 35 * 24 * 3600)

            quota = settings.tavily_monthly_quota
            pct_50 = int(quota * 0.5)
            pct_90 = int(quota * 0.9)

            # Check 50% threshold
            if current >= pct_50:
                alert_key = f"tavily:alert:sent:{month_key}:50pct"
                if r.setnx(alert_key, "1"):
                    r.expire(alert_key, 35 * 24 * 3600)
                    self._dispatch_alert("warning", current, quota)

            # Check 90% threshold
            if current >= pct_90:
                alert_key = f"tavily:alert:sent:{month_key}:90pct"
                if r.setnx(alert_key, "1"):
                    r.expire(alert_key, 35 * 24 * 3600)
                    self._dispatch_alert("critical", current, quota)

        except Exception as e:
            logger.error("Global counter increment failed: %s", e)

    def _dispatch_alert(self, level: str, usage: int, quota: int) -> None:
        """Dispatch alert via Celery (non-blocking)."""
        try:
            from app.tasks.ingestion import send_admin_alert
            send_admin_alert.delay(level, usage, quota)
            logger.info("Alert dispatched: level=%s, usage=%d/%d", level, usage, quota)
        except Exception as e:
            logger.warning("Alert dispatch failed (non-fatal): %s", e)

    # ── Read-Only Helpers ─────────────────────────────────────────────

    def get_global_monthly_usage(self) -> int:
        """Get current month's total Tavily usage."""
        r = self._get_redis()
        if r is None:
            return 0

        month_key = datetime.now(timezone.utc).strftime("%Y-%m")
        try:
            val = r.get(f"tavily:global:{month_key}")
            return int(val) if val else 0
        except Exception:
            return 0

    def get_next_reset_date(self) -> str:
        """Get the next monthly reset date as YYYY-MM-01 string."""
        now = datetime.now(timezone.utc)
        if now.month == 12:
            return f"{now.year + 1}-01-01"
        return f"{now.year}-{now.month + 1:02d}-01"

    # ── Tavily Failover Helpers ───────────────────────────────────────

    def is_tavily_key_exhausted(self, api_key: str) -> bool:
        """Check if a Tavily API key is marked as exhausted in Redis."""
        r = self._get_redis()
        if r is None:
            return False
        try:
            # We hash the key lightly or just use it directly (it's safe in Redis, but let's take a substring for the key name so it's not fully exposed in plain text if not needed)
            key_suffix = api_key[-8:] if len(api_key) > 8 else api_key
            return bool(r.get(f"tavily:exhausted:{key_suffix}"))
        except Exception:
            return False

    def mark_tavily_key_exhausted(self, api_key: str) -> None:
        """Mark a Tavily API key as permanently exhausted and send an alert."""
        # 1. Delete from running config memory to ensure it is not used again by this worker
        from app.config import settings
        if settings.tavily_api_key:
            keys = [k.strip() for k in settings.tavily_api_key.split(",") if k.strip()]
            if api_key in keys:
                keys.remove(api_key)
                settings.tavily_api_key = ",".join(keys)
                logger.warning("Deleted exhausted Tavily key from current worker config memory.")
                
        r = self._get_redis()
        if r is None:
            return
        try:
            key_suffix = api_key[-8:] if len(api_key) > 8 else api_key
            # Use setnx so we only trigger the alert once per key across all workers
            is_new = r.setnx(f"tavily:exhausted:{key_suffix}", "1")
            if is_new:
                logger.warning(f"Marked Tavily key (...{key_suffix}) as permanently exhausted in Redis.")
                from app.services.alert_service import alert_service
                alert_service.send_dead_key_alert(api_key)
        except Exception as e:
            logger.error("Failed to mark Tavily key as exhausted: %s", e)


# Singleton
usage_service = UsageService()
