import json
import os
import time
from uuid import uuid4

import httpx
import pytest

BENCHMARK_URL = os.getenv("BENCHMARK_URL", "http://localhost:9000")
CHAT_URL = f"{BENCHMARK_URL}/api/chat"
REQ_TIMEOUT = float(os.getenv("BENCHMARK_TIMEOUT", "120"))
TTFT_THRESHOLD_MS = float(os.getenv("TTFT_THRESHOLD_MS", "10000"))
TOTAL_THRESHOLD_MS = float(os.getenv("TOTAL_THRESHOLD_MS", "60000"))

integration = pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="Set RUN_INTEGRATION_TESTS=1 to run integration tests",
)


@integration
@pytest.mark.asyncio
@pytest.mark.parametrize("message,label", [
    ("hi", "greeting"),
    ("I got 4500 rank in CEE which colleges can I get", "prediction_simple"),
    ("I got 12000 rank in JEE general category which colleges can I get", "prediction_detailed"),
    ("rank 8500 cee can I get computer science", "prediction_filtered"),
    ("tell me about colleges", "ambiguous"),
    ("what is the weather today", "off_topic"),
])
async def test_chat_latency_within_bounds(message: str, label: str) -> None:
    session_id = f"latency-ci-{uuid4()}"
    payload = {"message": message, "session_id": session_id}

    async with httpx.AsyncClient(timeout=httpx.Timeout(REQ_TIMEOUT)) as client:
        start = time.monotonic()
        async with client.stream("POST", CHAT_URL, json=payload) as response:
            first_byte = time.monotonic()
            ttft_ms = (first_byte - start) * 1000

            found_done = False
            async for raw_line in response.aiter_lines():
                stripped = raw_line.strip()
                if stripped.startswith("data: "):
                    try:
                        event = json.loads(stripped[len("data: "):])
                        if event.get("type") == "done":
                            found_done = True
                            break
                    except json.JSONDecodeError:
                        pass

            total_ms = (time.monotonic() - start) * 1000
            response_time_header = response.headers.get("x-response-time-ms")

    assert response.status_code == 200, f"[{label}] HTTP {response.status_code}"
    assert found_done, f"[{label}] SSE done event not received"
    assert ttft_ms < TTFT_THRESHOLD_MS, (
        f"[{label}] TTFT {ttft_ms:.0f}ms exceeded {TTFT_THRESHOLD_MS:.0f}ms threshold"
    )
    assert total_ms < TOTAL_THRESHOLD_MS, (
        f"[{label}] Total {total_ms:.0f}ms exceeded {TOTAL_THRESHOLD_MS:.0f}ms threshold"
    )
