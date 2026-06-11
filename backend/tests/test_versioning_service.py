import pytest
from app.services.versioning_service import VersioningService


@pytest.fixture
def vs():
    svc = VersioningService()
    return svc


class TestRegisterAndGet:
    def test_register_and_get_current(self, vs):
        vs.register("test_policy", "v1", {"rule": "x"})
        entry = vs.get_current("test_policy")
        assert entry is not None
        assert entry.version == "v1"

    def test_get_missing_returns_none(self, vs):
        assert vs.get_current("no_such_key") is None

    def test_get_history_after_register(self, vs):
        vs.register("test_policy", "v1", {"rule": "x"})
        hist = vs.get_history("test_policy")
        assert len(hist) == 1


class TestVersionTracking:
    def test_multiple_versions(self, vs):
        vs.register("test_policy", "v1", "first")
        vs.register("test_policy", "v2", "second")
        current = vs.get_current("test_policy")
        assert current.version == "v2"
        assert current.content == "second"

    def test_history_preserves_all(self, vs):
        vs.register("test_policy", "v1", "a")
        vs.register("test_policy", "v2", "b")
        hist = vs.get_history("test_policy")
        assert len(hist) == 2


class TestRollback:
    def test_rollback_to_previous(self, vs):
        vs.register("test_policy", "v1", "original")
        vs.register("test_policy", "v2", "updated")
        assert vs.rollback("test_policy", "v1") is True
        entry = vs.get_current("test_policy")
        assert entry.version == "v1"
        assert entry.content == "original"

    def test_rollback_unknown_version(self, vs):
        vs.register("test_policy", "v1", "x")
        assert vs.rollback("test_policy", "v99") is False

    def test_rollback_missing_policy(self, vs):
        assert vs.rollback("missing", "v1") is False


class TestGetAllCurrent:
    def test_get_all_current_includes_defaults(self, vs):
        all_ver = vs.get_all_current()
        assert "routing_policy" in all_ver
        assert "budget_policy" in all_ver

    def test_get_all_current_includes_custom(self, vs):
        vs.register("custom_pol", "v1", {"x": 1})
        all_ver = vs.get_all_current()
        assert "custom_pol" in all_ver
        assert all_ver["custom_pol"]["version"] == "v1"
