import asyncio
from app.orchestration.orchestrator import supreme_orchestrator

async def test_hello():
    result = await supreme_orchestrator.handle_request('Hello', [], 'test-session')
    print('HELLO RESULT:', result.get('content'))

asyncio.run(test_hello())
