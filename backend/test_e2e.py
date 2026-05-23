import asyncio
import sys
import os

# Fix windows emoji print crash
sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.orchestration.orchestrator import supreme_orchestrator

async def run_test(query: str, session_id: str):
    print(f"\n[{session_id}] QUERY: {query}")
    print("-" * 50)
    result = await supreme_orchestrator.handle_request(query, [], session_id)
    
    # We want to print the response cleanly
    print(f"RESPONSE:\n{result.get('content')}")
    print("-" * 50)
    
    # Check if there is trace data attached
    if "trace" in result:
        trace = result["trace"]
        print(f"INTENT: {trace.get('intent')}")
        print(f"AGENTS USED: {trace.get('agents_used', [])}")
        print(f"SOURCES USED: {trace.get('sources_used', [])}")
        if trace.get('fallback_reason'):
            print(f"FALLBACK TRIGGERED: {trace['fallback_reason']}")
    print("=" * 70)

async def main():
    queries = [
        ("Hello RankRoute! How are you?", "test_greeting"),
        ("I have a rank of 350 in CEE (General). Can I get Computer Science in AEC or JEC?", "test_prediction"),
        ("What are the hostel facilities like at AEC?", "test_local_web"),
        ("What is the latest admission news for NIT Silchar?", "test_tavily_fallback")
    ]
    
    for query, session_id in queries:
        await run_test(query, session_id)

if __name__ == "__main__":
    asyncio.run(main())
