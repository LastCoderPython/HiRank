import asyncio
import sys

sys.path.insert(0, r'd:\Fusion-Focus\rankroute\backend')
from app.api.chat import _generate_stream
from app.services.cache_service import cache_service

async def test():
    print("Testing Deep Research Polling...")
    async for chunk in _generate_stream('I need deep research on this', [], 'test-session'):
        print(chunk.strip())
        
    print("\nTesting State Machine...")
    async for chunk in _generate_stream('predict my rank and document', [], 'test-session-2'):
        pass
    print('State:', cache_service.get('journey', 'test-session-2'))

if __name__ == "__main__":
    asyncio.run(test())
