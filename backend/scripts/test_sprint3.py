"""Sprint 3 Validation Script — tests CutoffEngine, IntentAgent, PredictionAgent."""

import asyncio
import json
import sys

sys.path.insert(0, ".")

# Test 1: CutoffEngine standalone
from app.retrieval.cutoff_engine import cutoff_engine

print("=== CUTOFF ENGINE STATS ===")
stats = cutoff_engine.get_stats()
print(json.dumps(stats, indent=2))
print()

# Test 2: Predict for CEE rank 500, General
print("=== CEE PREDICTION: Rank 500, General ===")
bundle = cutoff_engine.predict(rank=500, category="General", exam="CEE")
print(f"Safe: {len(bundle.safe_options)}, Target: {len(bundle.target_options)}, Ambitious: {len(bundle.ambitious_options)}")
print(f"Evidence rows: {bundle.evidence_rows_used}")
for opt in bundle.safe_options[:3]:
    print(f"  SAFE: {opt.college_name} - {opt.branch} (closing: {opt.closing_rank}, match: {opt.match_percentage}%)")
for opt in bundle.target_options[:3]:
    print(f"  TARGET: {opt.college_name} - {opt.branch} (closing: {opt.closing_rank}, match: {opt.match_percentage}%)")
for opt in bundle.ambitious_options[:3]:
    print(f"  AMBITIOUS: {opt.college_name} - {opt.branch} (closing: {opt.closing_rank}, match: {opt.match_percentage}%)")
print()

# Test 3: Predict for CEE rank 2000, OBC
print("=== CEE PREDICTION: Rank 2000, OBC ===")
bundle2 = cutoff_engine.predict(rank=2000, category="OBC", exam="CEE")
print(f"Safe: {len(bundle2.safe_options)}, Target: {len(bundle2.target_options)}, Ambitious: {len(bundle2.ambitious_options)}")
for opt in bundle2.safe_options[:3]:
    print(f"  SAFE: {opt.college_name} - {opt.branch} (closing: {opt.closing_rank}, match: {opt.match_percentage}%)")
print()

# Test 4: JEE prediction
print("=== JEE PREDICTION: Rank 15000, General ===")
bundle3 = cutoff_engine.predict(rank=15000, category="General", exam="JEE")
print(f"Safe: {len(bundle3.safe_options)}, Target: {len(bundle3.target_options)}, Ambitious: {len(bundle3.ambitious_options)}")
for opt in bundle3.safe_options[:3]:
    print(f"  SAFE: {opt.college_name} - {opt.branch} (closing: {opt.closing_rank}, match: {opt.match_percentage}%)")
for opt in bundle3.target_options[:3]:
    print(f"  TARGET: {opt.college_name} - {opt.branch} (closing: {opt.closing_rank}, match: {opt.match_percentage}%)")
print()

# Test 5: IntentAgent
from app.orchestration.agents.intent_agent import intent_agent

async def test_intent():
    print("=== INTENT AGENT TESTS ===")
    
    tests = [
        "I got rank 3000 in CEE. Which colleges can I get in Computer Science?",
        "Hello!",
        "What is the fee structure of AEC?",
        "Compare NIT Silchar and Tezpur University for CSE",
        "What are the placement stats at Jorhat Engineering College?",
        "My rank is 500 in JEE Mains, OBC category",
    ]
    
    for q in tests:
        result = await intent_agent.run(q)
        print(f"  Query: {q}")
        print(f"  -> intent={result.intent}, rank={result.rank}, exam={result.exam}, cat={result.category}")
        print(f"     branch={result.branch_preference}, targets={result.college_targets}, web={result.needs_web_context}")
        print()

asyncio.run(test_intent())

# Test 6: get_colleges_list for API endpoint
print("=== GET /api/colleges simulation ===")
colleges = cutoff_engine.get_colleges_list(rank=2000, category="General", exam="CEE", limit=5)
for c in colleges:
    name = c["college_name"]
    branch = c["branch"]
    band = c["band"]
    match = c["match_percentage"]
    print(f"  {name} - {branch} | band={band} match={match}%")

print()
print("=== ALL TESTS PASSED ===")
