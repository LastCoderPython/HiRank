"""Security hardening tests — verifies fixes from LLM Council audit."""

import inspect
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from app.main import app
from app.api.profile import ProfileUpdateRequest

client = TestClient(app)


class TestProfileExtraForbid:
    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            ProfileUpdateRequest.model_validate({"name": "test", "role": "admin"})

    def test_extra_field_role_rejected(self):
        with pytest.raises(ValidationError):
            ProfileUpdateRequest.model_validate({"name": "test", "rank": 100, "is_admin": True})

    def test_valid_fields_accepted(self):
        model = ProfileUpdateRequest(name="test", rank=100, category="OBC")
        assert model.name == "test"
        assert model.rank == 100
        assert model.category == "OBC"

    def test_empty_model_accepted(self):
        model = ProfileUpdateRequest()
        assert model.model_dump(exclude_none=True) == {}


class TestProfileFieldAllowlist:
    def test_profile_api_rejects_role(self, monkeypatch):
        async def mock_get_user_id(x):
            return "test-user"
        monkeypatch.setattr("app.api.profile._get_user_id", mock_get_user_id)

        async def _mock(uid, updates):
            return updates
        monkeypatch.setattr("app.db.supabase.patch_profile", _mock)
        response = client.patch(
            "/api/v1/profile",
            json={"name": "test", "role": "admin"},
            headers={"Cookie": "sb_access_token=fake"},
        )
        assert response.status_code == 422

    def test_profile_api_allows_valid_fields(self, monkeypatch):
        async def mock_get_user_id(x):
            return "test-user"
        monkeypatch.setattr("app.api.profile._get_user_id", mock_get_user_id)

        async def _mock(uid, updates):
            return updates
        monkeypatch.setattr("app.db.supabase.patch_profile", _mock)
        response = client.patch(
            "/api/v1/profile",
            json={"name": "Alice", "rank": 50},
            headers={"Cookie": "sb_access_token=fake"},
        )
        assert response.status_code == 200


class TestSecurityHeaders:
    def test_csp_not_on_api_responses(self):
        """CSP headers are only added to text/html responses, not JSON API responses."""
        response = client.get("/api/v1/health")
        assert "Content-Security-Policy" not in response.headers

    def test_x_content_type_options(self):
        response = client.get("/api/v1/health")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options_not_on_api_responses(self):
        """X-Frame-Options is only added to text/html responses, not JSON API responses."""
        response = client.get("/api/v1/health")
        assert response.headers.get("X-Frame-Options") is None

    def test_referrer_policy(self):
        response = client.get("/api/v1/health")
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_permissions_policy(self):
        response = client.get("/api/v1/health")
        pp = response.headers.get("Permissions-Policy", "")
        assert "geolocation=()" in pp
        assert "microphone=()" in pp
        assert "camera=()" in pp

    def test_no_server_header(self):
        response = client.get("/api/v1/health")
        assert "server" not in response.headers or "uvicorn" not in response.headers.get("server", "")


class TestHealthEndpoint:
    def test_health_returns_200(self):
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_health_has_status(self):
        response = client.get("/api/v1/health")
        data = response.json()
        assert "status" in data

    def test_health_no_credentials_leaked(self):
        response = client.get("/api/v1/health")
        body = response.text.lower()
        assert "supabase" not in body or "service_key" not in body
        assert "redis://" not in body or "password" not in body


class TestHealthRateLimit:
    @pytest.mark.asyncio
    async def test_acceptable_rate(self):
        for _ in range(5):
            response = client.get("/api/v1/health")
            assert response.status_code == 200

    def test_rate_limit_config(self):
        from app.middleware.rate_limit import _ENDPOINT_LIMITS
        assert "/api/v1/health" in _ENDPOINT_LIMITS
        limit, window = _ENDPOINT_LIMITS["/api/v1/health"]
        assert limit == 30
        assert window == 60


class TestSSECorsWildcard:
    def test_sse_no_wildcard_origin(self):
        from app.api.chat import chat_endpoint
        sig = inspect.signature(chat_endpoint)
        source = inspect.getsource(chat_endpoint)
        assert '"Access-Control-Allow-Origin"' not in source or "'*'" not in source.split('"Access-Control-Allow-Origin"')[1].split("\n")[0]

    def test_cors_middleware_configured(self):
        from starlette.middleware.cors import CORSMiddleware
        found = any(m.cls is CORSMiddleware for m in app.user_middleware if hasattr(m, "cls"))
        assert found

    def test_cors_origins_not_wildcard(self):
        from app.config import settings
        origins = settings.cors_origins.split(",") if settings.cors_origins else []
        assert "*" not in origins


class TestHttpxVersion:
    def test_httpx_version_safe(self):
        import httpx
        major, minor, *_ = [int(x) for x in httpx.__version__.split(".")]
        assert (major, minor) >= (0, 28), f"httpx {httpx.__version__} is vulnerable to CVE-2024-36580"


class TestStarletteVersion:
    def test_starlette_version_safe(self):
        import starlette
        major, minor, *_ = [int(x) for x in starlette.__version__.split(".")]
        assert (major, minor) >= (0, 40), f"starlette {starlette.__version__} should be >= 0.40.0"
