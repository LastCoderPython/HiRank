import asyncio
from app.orchestration.orchestrator import supreme_orchestrator

async def test_fee():
    result = await supreme_orchestrator.handle_request('What are the fees for AEC?', [], 'test-session-1')
    print('FEE TEST RESULT:', result.get('content'))

async def test_tavily():
    result = await supreme_orchestrator.handle_request('What are the latest admission updates for AEC in 2024?', [], 'test-session-2')
    print('TAVILY TEST RESULT:', result.get('content'))

asyncio.run(test_fee())
asyncio.run(test_tavily())
