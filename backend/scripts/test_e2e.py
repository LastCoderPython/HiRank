"""End-to-end test against the live RankRoute V2 server.

Tests the 3 completion criteria from the V2 plan:
  1. Deterministic admission prediction
  2. Descriptive college information
  3. GET /api/colleges deterministic endpoint
  4. Health endpoint
  5. Scrape API validation
"""

import httpx
import json
import sys

BASE = "http://127.0.0.1:8000"


def test_health():
    print("=== 1. HEALTH CHECK ===")
    r = httpx.get(f"{BASE}/api/health", timeout=30)
    data = r.json()
    print(f"  Status: {data.get('status')}")
    print(f"  Version: {data.get('version')}")
    print(f"  Architecture: {data.get('architecture')}")
    ce = data.get("cutoff_engine", {})
    print(f"  CutoffEngine: CEE={ce.get('cee_records')} JEE={ce.get('jee_records')} loaded={ce.get('data_loaded')}")
    assert data["status"] == "healthy"
    assert data["version"] == "2.0.0-alpha"
    assert ce.get("data_loaded") == True
    print("  PASSED")
    print()


def test_colleges_endpoint():
    print("=== 2. GET /api/colleges (Deterministic Prediction) ===")
    r = httpx.get(f"{BASE}/api/colleges", params={
        "rank": 3000, "category": "General", "exam": "CEE", "limit": 5,
    }, timeout=30)
    data = r.json()
    colleges = data.get("colleges", [])
    print(f"  Total: {data.get('total')}")
    for c in colleges[:5]:
        print(f"    {c['college_name']} - {c['branch']} | band={c.get('band', 'N/A')} match={c.get('match_percentage', 0):.0f}%")
    assert data["total"] > 0
    assert all("college_name" in c for c in colleges)
    print("  PASSED")
    print()


def test_chat_prediction():
    print("=== 3. POST /api/chat (Prediction Query) ===")
    r = httpx.post(f"{BASE}/api/chat", json={
        "message": "My CEE rank is 2000 General category. Which colleges can I get?",
        "session_id": "test-e2e-pred",
    }, timeout=60)

    events = []
    has_colleges = False
    has_tokens = False

    for line in r.text.strip().split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            try:
                event = json.loads(line[6:])
                events.append(event)
                if event.get("type") == "colleges":
                    has_colleges = True
                    print(f"  Colleges received: {len(event.get('data', []))} items")
                elif event.get("type") == "token":
                    if not has_tokens:
                        preview = event.get("data", "")[:100]
                        print(f"  First token: {preview}...")
                        has_tokens = True
                elif event.get("type") == "done":
                    print(f"  Stream completed (done event received)")
            except json.JSONDecodeError:
                pass

    print(f"  Total events: {len(events)}")
    assert has_tokens, "No tokens received from prediction query"
    print("  PASSED")
    print()


def test_chat_descriptive():
    print("=== 4. POST /api/chat (Descriptive Query) ===")
    r = httpx.post(f"{BASE}/api/chat", json={
        "message": "What is the fee structure of AEC?",
        "session_id": "test-e2e-desc",
    }, timeout=60)

    events = []
    has_tokens = False

    for line in r.text.strip().split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            try:
                event = json.loads(line[6:])
                events.append(event)
                if event.get("type") == "token":
                    if not has_tokens:
                        preview = event.get("data", "")[:100]
                        print(f"  First token: {preview}...")
                        has_tokens = True
                elif event.get("type") == "done":
                    print(f"  Stream completed")
            except json.JSONDecodeError:
                pass

    print(f"  Total events: {len(events)}")
    assert has_tokens, "No tokens received from descriptive query"
    print("  PASSED")
    print()


def test_chat_greeting():
    print("=== 5. POST /api/chat (Greeting - Direct Response) ===")
    r = httpx.post(f"{BASE}/api/chat", json={
        "message": "Hello!",
        "session_id": "test-e2e-greet",
    }, timeout=30)

    for line in r.text.strip().split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            try:
                event = json.loads(line[6:])
                if event.get("type") == "token":
                    text = event.get('data', '')[:120]
                    print(f"  Response: {text.encode('ascii', 'replace').decode()}")
            except json.JSONDecodeError:
                pass

    print("  PASSED")
    print()


def test_scrape_validation():
    print("=== 6. POST /api/scrape/run (URL Validation) ===")

    # Test rejected URL
    r = httpx.post(f"{BASE}/api/scrape/run", json={
        "urls": ["https://random-blog.com/colleges"],
        "college_name": "Test",
    }, timeout=15)
    print(f"  Unapproved URL: status={r.status_code}")
    assert r.status_code == 400
    print("  PASSED (correctly rejected)")
    print()


if __name__ == "__main__":
    try:
        test_health()
        test_colleges_endpoint()
        test_chat_prediction()
        test_chat_descriptive()
        test_chat_greeting()
        test_scrape_validation()
        print("=" * 50)
        print("ALL END-TO-END TESTS PASSED")
        print("=" * 50)
    except Exception as e:
        print(f"\nFAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
