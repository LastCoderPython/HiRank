"""Sprint 5-6 Validation Script — tests all new modules."""

import asyncio
import sys
sys.path.insert(0, ".")


def test_imports():
    """Test that every new module imports without errors."""
    print("=== MODULE IMPORTS ===")
    
    # Orchestration layer
    from app.orchestration.routing_policy import routing_policy
    from app.orchestration.source_policy import source_policy
    from app.orchestration.budget_policy import budget_policy
    from app.orchestration.retrieval_policy import retrieval_policy
    from app.orchestration.verification_policy import verification_policy
    from app.orchestration.fallback_policy import fallback_policy
    from app.orchestration.traces import RequestTrace
    from app.orchestration.types import RequestFrame, PredictionAgentOutput, WebKnowledgeOutput
    print("  [OK] orchestration policies + types")
    
    # Agents
    from app.orchestration.agents.intent_agent import intent_agent
    from app.orchestration.agents.structured_prediction_agent import structured_prediction_agent
    from app.orchestration.agents.web_knowledge_agent import web_knowledge_agent
    from app.orchestration.agents.verifier_agent import verifier_agent
    print("  [OK] all 4 agents")
    
    # Retrieval
    from app.retrieval.cutoff_engine import cutoff_engine
    from app.retrieval.metadata_filters import build_college_filter, intent_to_page_types
    print("  [OK] retrieval (cutoff engine + metadata filters)")
    
    # Ingestion
    from app.ingestion.scrape_runner import fetch_page, is_approved_url
    from app.ingestion.page_cleaner import clean_page
    from app.ingestion.chunker import chunk_text
    from app.ingestion.embedder import embed_chunks
    from app.ingestion.upsert_service import upsert_chunks
    print("  [OK] ingestion pipeline (5 modules)")
    
    # Orchestrator (imports all agents internally)
    from app.orchestration.orchestrator import supreme_orchestrator
    print("  [OK] Supreme Orchestrator (all agents wired)")
    
    # API routes
    from app.api.chat import router as chat_router
    from app.api.scrape import router as scrape_router
    print("  [OK] API routes (chat + scrape)")
    
    print()
    return True


def test_metadata_filters():
    """Test metadata filter construction."""
    print("=== METADATA FILTERS ===")
    from app.retrieval.metadata_filters import build_college_filter, intent_to_page_types
    
    f1 = build_college_filter(college_names=["JEC"], page_types=["hostel"])
    print(f"  JEC hostel: {f1}")
    assert f1 == {"$and": [{"college_name": "JEC"}, {"page_type": "hostel"}]}
    
    f2 = build_college_filter(college_names=["AEC"], is_official=True, page_types=["placement"])
    print(f"  AEC placement (official): {f2}")
    assert "$and" in f2
    
    f3 = build_college_filter(college_names=["AEC", "JEC"])
    print(f"  Multi-college: {f3}")
    
    types = intent_to_page_types("fee_inquiry")
    print(f"  fee_inquiry -> page_types: {types}")
    assert "fees" in types
    
    print("  [OK] all filter tests passed")
    print()


def test_scrape_runner():
    """Test URL approval logic."""
    print("=== SCRAPE RUNNER ===")
    from app.ingestion.scrape_runner import is_approved_url
    
    assert is_approved_url("https://www.aec.ac.in/placements") == True
    assert is_approved_url("https://www.nits.ac.in/fees") == True
    assert is_approved_url("https://random-blog.com/colleges") == False
    assert is_approved_url("https://coaching-portal.in/rank") == False
    print("  [OK] approved/rejected URL checks passed")
    print()


def test_page_cleaner():
    """Test HTML cleaning and page type classification."""
    print("=== PAGE CLEANER ===")
    from app.ingestion.page_cleaner import clean_page
    
    html = """
    <html><head><title>AEC Placements 2024</title></head>
    <body>
    <nav>Home | About | Contact</nav>
    <div>
        <h1>Placement Statistics 2024</h1>
        <p>Our students received excellent campus placement offers from top recruiters. 
        The average package was 6.5 LPA with the highest package of 22 LPA.</p>
        <p>Major recruiters include TCS, Infosys, Wipro, and Amazon.</p>
    </div>
    <footer>© 2024 AEC. All rights reserved.</footer>
    </body></html>
    """
    
    result = clean_page(html)
    print(f"  Title: {result.title}")
    print(f"  Page type: {result.page_type}")
    print(f"  Words: {result.word_count}")
    print(f"  Text preview: {result.text[:120]}...")
    assert result.page_type == "placement"
    assert result.word_count > 10
    print("  [OK] page cleaning + classification passed")
    print()


def test_chunker():
    """Test text chunking."""
    print("=== CHUNKER ===")
    from app.ingestion.chunker import chunk_text
    
    text = (
        "PLACEMENT STATISTICS: Our college has a strong placement record. "
        "The average package for 2024 batch was 6.5 LPA. Major recruiters "
        "include TCS, Infosys, Wipro, Amazon, and Google. Over 85% of students "
        "were placed in the first round of campus recruitment drives. "
        "The highest package offered was 22 LPA by Amazon. "
        "\n\n"
        "FEE STRUCTURE: The total fee for the first year is Rs 75000. "
        "This includes tuition fee, hostel fee, and examination fee. "
        "Students from SC/ST categories receive fee waivers as per government norms."
    )
    
    chunks = chunk_text(text, max_chunk_chars=300)
    print(f"  Input: {len(text)} chars")
    print(f"  Chunks: {len(chunks)}")
    for c in chunks:
        print(f"    [{c.chunk_index}] heading='{c.heading}' chars={c.char_count} hash={c.content_hash}")
    assert len(chunks) >= 1
    print("  [OK] chunking passed")
    print()


def test_verifier():
    """Test the verifier agent."""
    print("=== VERIFIER AGENT ===")
    from app.orchestration.agents.verifier_agent import verifier_agent
    from app.orchestration.types import RequestFrame, PredictionAgentOutput, WebKnowledgeOutput
    
    async def run_tests():
        # Test 1: prediction with evidence -> approved
        frame = RequestFrame(intent="college_prediction", rank=3000, exam="CEE")
        pred = PredictionAgentOutput(evidence_rows_used=5)
        result = await verifier_agent.run(frame=frame, prediction=pred)
        print(f"  Prediction with evidence: approved={result.approved}, issues={result.issues}")
        assert result.approved == True
        
        # Test 2: prediction without evidence -> blocked
        frame2 = RequestFrame(intent="college_prediction", rank=3000, exam="CEE")
        pred2 = PredictionAgentOutput(evidence_rows_used=0)
        result2 = await verifier_agent.run(frame=frame2, prediction=pred2)
        print(f"  Prediction without evidence: approved={result2.approved}, issues={result2.issues}")
        assert result2.approved == False
        
        # Test 3: descriptive with web evidence -> approved
        frame3 = RequestFrame(intent="fee_inquiry", college_targets=["AEC"], needs_web_context=True)
        web = WebKnowledgeOutput(sources_used=3)
        result3 = await verifier_agent.run(frame=frame3, web_knowledge=web)
        print(f"  Fee inquiry with web data: approved={result3.approved}, issues={result3.issues}")
        assert result3.approved == True
    
    asyncio.run(run_tests())
    print("  [OK] verifier tests passed")
    print()


def test_orchestrator_wiring():
    """Verify the orchestrator has all 4 agents wired."""
    print("=== ORCHESTRATOR WIRING ===")
    from app.orchestration.orchestrator import supreme_orchestrator as orch
    
    assert orch._intent_agent is not None, "IntentAgent not wired"
    assert orch._prediction_agent is not None, "PredictionAgent not wired"
    assert orch._web_knowledge_agent is not None, "WebKnowledgeAgent not wired"
    assert orch._verifier_agent is not None, "VerifierAgent not wired"
    
    print("  [OK] IntentAgent")
    print("  [OK] StructuredPredictionAgent")
    print("  [OK] WebKnowledgeAgent")
    print("  [OK] VerifierAgent")
    print()


if __name__ == "__main__":
    test_imports()
    test_metadata_filters()
    test_scrape_runner()
    test_page_cleaner()
    test_chunker()
    test_verifier()
    test_orchestrator_wiring()
    print("=" * 50)
    print("ALL SPRINT 5-6 TESTS PASSED")
    print("=" * 50)
