import asyncio
import logging
logging.basicConfig(level=logging.DEBUG)

from app.orchestration.orchestrator import supreme_orchestrator
from app.config import settings
print("TAVILY_API_KEY:", settings.tavily_api_key)

async def test_tavily():
    print("Testing Tavily live web search...")
    result = await supreme_orchestrator.handle_request('What are the latest admission updates for AEC in 2024?', [], 'test-session-2')
    print('TAVILY TEST RESULT:', result.get('content').encode('utf-8', errors='ignore'))

asyncio.run(test_tavily())
