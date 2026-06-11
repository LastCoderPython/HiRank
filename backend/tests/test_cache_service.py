import time
import pytest
from app.services.cache_service import CacheService


@pytest.fixture
def cache():
    svc = CacheService()
    svc.clear()
    return svc


class TestCacheSetAndGet:
    def test_set_and_get(self, cache):
        cache.set("test_ns", "key1", "value1")
        assert cache.get("test_ns", "key1") == "value1"

    def test_get_missing(self, cache):
        assert cache.get("test_ns", "missing") is None

    def test_overwrite(self, cache):
        cache.set("test_ns", "key", "old")
        cache.set("test_ns", "key", "new")
        assert cache.get("test_ns", "key") == "new"


class TestCacheTTL:
    def test_expired_entry_returns_none(self, cache):
        cache.set("test_ns", "short", "value", ttl=0.1)
        time.sleep(0.15)
        assert cache.get("test_ns", "short") is None

    def test_fresh_entry_returns_value(self, cache):
        cache.set("test_ns", "long", "value", ttl=10)
        assert cache.get("test_ns", "long") == "value"

    def test_namespace_default_ttl(self, cache):
        cache.set("intent", "q", "parsed")
        assert cache.get("intent", "q") == "parsed"


class TestCacheInvalidate:
    def test_invalidate_key(self, cache):
        cache.set("test_ns", "del_me", "value")
        cache.invalidate("test_ns", "del_me")
        assert cache.get("test_ns", "del_me") is None

    def test_invalidate_namespace(self, cache):
        cache.set("test_ns", "a", 1)
        cache.set("test_ns", "b", 2)
        cache.invalidate("test_ns")
        assert cache.get("test_ns", "a") is None
        assert cache.get("test_ns", "b") is None


class TestCacheClear:
    def test_clear_removes_all(self, cache):
        cache.set("ns1", "a", 1)
        cache.set("ns2", "b", 2)
        cache.clear()
        assert cache.get("ns1", "a") is None
        assert cache.get("ns2", "b") is None


class TestCacheMakeKey:
    def test_make_key_from_parts(self):
        key = CacheService.make_key("rank", "123", "CS")
        assert isinstance(key, str)
        assert len(key) == 24

    def test_make_key_strips_none(self):
        key = CacheService.make_key("a", None, "c")
        assert isinstance(key, str)


class TestCacheStats:
    def test_stats_after_set_and_get(self, cache):
        cache.set("test_ns", "x", 1)
        cache.get("test_ns", "x")
        stats = cache.get_stats()
        assert stats["hits"] >= 1

    def test_stats_after_miss(self, cache):
        cache.get("test_ns", "nobody")
        stats = cache.get_stats()
        assert stats["misses"] >= 1

    def test_stats_has_namespaces(self, cache):
        cache.set("test_ns", "x", 1)
        stats = cache.get_stats()
        assert "namespaces" in stats
