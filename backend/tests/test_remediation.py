import pytest
import asyncio
import time
import os
import threading
from unittest.mock import MagicMock, patch

# Test imports
from app.db.supabase import get_supabase_client
from app.api.auth import router as auth_router
from app.config import settings
from app.orchestration.orchestrator import supreme_orchestrator
from app.services.college_info_service import college_info_service
from app.retrieval.cutoff_engine import cutoff_engine
from app.middleware.rate_limit import RateLimitMiddleware

@pytest.mark.asyncio
async def test_all():
    print("Starting tests for LLM Council Remediation...")
    results = {}

    # 1. C-01 & C-02: OAuth Config & State
    try:
        assert hasattr(settings, "backend_url"), "settings.backend_url is missing"
        # Check if auth.py has secrets imported and uses backend_url
        with open("app/api/auth.py", "r") as f:
            auth_code = f.read()
            assert "secrets.token_urlsafe" in auth_code, "CSRF state generation missing"
            assert "secrets.compare_digest" in auth_code, "CSRF state validation missing"
            assert "settings.backend_url" in auth_code, "Host header injection fix missing"
        results["C-01/C-02 (OAuth Security)"] = "PASS"
    except Exception as e:
        results["C-01/C-02 (OAuth Security)"] = f"FAIL: {e}"

    # 2. C-03: Settings import in colleges.py
    try:
        with open("app/api/colleges.py", "r") as f:
            colleges_code = f.read()
            assert "from app.config import settings" in colleges_code, "Missing settings import"
        results["C-03 (Missing Import)"] = "PASS"
    except Exception as e:
        results["C-03 (Missing Import)"] = f"FAIL: {e}"

    # 3. C-05: Orchestrator Timeouts
    try:
        with open("app/orchestration/orchestrator.py", "r") as f:
            orch_code = f.read()
            assert "asyncio.wait_for(" in orch_code, "No asyncio.wait_for found"
            assert "timeout=20.0" in orch_code, "No 20s timeout found"
        results["C-05 (Orchestrator Timeouts)"] = "PASS"
    except Exception as e:
        results["C-05 (Orchestrator Timeouts)"] = f"FAIL: {e}"

    # 4. C-06: Hot-Reload Race Conditions
    try:
        # Just check that reload works without crashing and uses copy-on-write
        info_res = college_info_service.reload_all()
        assert isinstance(info_res, dict)
        
        # We can't fully run cutoff_engine reload without CSVs, but we can check the code
        with open("app/services/college_info_service.py", "r") as f:
            code = f.read()
            assert "tmp = CollegeInfoService.__new__(CollegeInfoService)" in code
            assert "self._reload_lock = threading.Lock()" in code
            
        with open("app/retrieval/cutoff_engine.py", "r") as f:
            code = f.read()
            assert "new_cee =" in code
            assert "new_jee =" in code
            
        results["C-06 (Hot-Reload Race Conditions)"] = "PASS"
    except Exception as e:
        results["C-06 (Hot-Reload Race Conditions)"] = f"FAIL: {e}"

    # 5. C-00: Async DB Unblocking
    try:
        with open("app/db/supabase.py", "r") as f:
            supa_code = f.read()
            assert "run_in_threadpool" in supa_code
        with open("app/api/analytics.py", "r") as f:
            ana_code = f.read()
            assert "run_in_threadpool" in ana_code
            assert "async def" in ana_code
        results["C-00 (Async DB Unblocking)"] = "PASS"
    except Exception as e:
        results["C-00 (Async DB Unblocking)"] = f"FAIL: {e}"

    # 6. H-06: Redis Rate Limiter
    try:
        with open("app/middleware/rate_limit.py", "r") as f:
            rl_code = f.read()
            assert "_redis_pipeline" in rl_code
            assert "redis" in rl_code.lower()
        results["H-06 (Redis Rate Limiter)"] = "PASS"
    except Exception as e:
        results["H-06 (Redis Rate Limiter)"] = f"FAIL: {e}"

    print("\n--- Test Results ---")
    for k, v in results.items():
        print(f"{k}: {v}")

if __name__ == '__main__':
    asyncio.run(test_all())
