import sys
sys.path.insert(0, ".")

print("Testing backend endpoints...")

# Test 1: Health check
import requests
try:
    resp = requests.get("http://localhost:8000/api/health", timeout=5)
    print(f"Health check: {resp.status_code}")
    print(resp.json())
except Exception as e:
    print(f"Health check failed: {e}")

# Test 2: Colleges endpoint
try:
    resp = requests.get("http://localhost:8000/api/colleges?rank=3000&category=General", timeout=10)
    print(f"Colleges endpoint: {resp.status_code}")
    print(resp.json())
except Exception as e:
    print(f"Colleges endpoint failed: {e}")

# Test 3: Chat endpoint (streaming)
try:
    resp = requests.post(
        "http://localhost:8000/api/chat",
        json={"message": "My rank is 3000 in CEE"},
        stream=True,
        timeout=30
    )
    print(f"Chat endpoint: {resp.status_code}")
    for line in resp.iter_lines():
        if line:
            print(line.decode())
            break
except Exception as e:
    print(f"Chat endpoint failed: {e}")
