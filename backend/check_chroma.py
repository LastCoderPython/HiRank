import os
import asyncio
from app.core.chroma_client import chroma_client

async def main():
    # Force initialization
    collection = chroma_client.get_collection()
    
    # Check count
    count = collection.count()
    print(f"Total documents in ChromaDB: {count}")
    
    # Get some documents
    if count > 0:
        results = collection.get(limit=10)
        for i, meta in enumerate(results["metadatas"]):
            print(f"Doc {i}: {meta.get('source_url', 'no url')} | College: {meta.get('college', 'no college')}")

if __name__ == "__main__":
    asyncio.run(main())
