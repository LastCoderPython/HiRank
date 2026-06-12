import asyncio
import sys

sys.path.insert(0, r'd:\Fusion-Focus\rankroute\backend')

from app.orchestration.orchestrator import supreme_orchestrator

async def test_rag():
    print("Testing Web Knowledge Agent (RAG) Retrieval...")
    query = "What are the hostel facilities at AEC?"
    print(f"Query: {query}")
    
    # We want to see if the orchestrator successfully pulls from ChromaDB
    try:
        result = await supreme_orchestrator.handle_request(query, [], "test-user", "test-session")
        print("\n--- FINAL CONTEXT PROVIDED TO LLM ---")
        print(result["content"])
        
        print("\n--- RETRIEVAL SOURCES ---")
        if "trace" in result:
            trace = result["trace"]
            print(f"Agents Used: {trace.get('agents_used', [])}")
            print(f"Retrieval Sources: {trace.get('retrieval_sources', [])}")
            print(f"Chroma Hits: {trace.get('chroma_hits', 0)}")
            
            # Print specific chunk metadata if available
            print("\n--- EVIDENCE (If any) ---")
            for chunk in result.get("colleges", []):
                print(chunk)
                
    except Exception as e:
        print(f"\n❌ Error during RAG test: {e}")

if __name__ == "__main__":
    asyncio.run(test_rag())
