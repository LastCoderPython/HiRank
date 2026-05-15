from app.core.chroma_client import chroma_client

print("=== JEE Rank 22000 General - Full Results ===")
results = chroma_client.query_by_rank(rank=22000, category='General', collection_name='jee', n_results=30)
print(f"Total results: {len(results)}")
for r in results:
    m = r['metadata']
    print(f"{m['college_name']} - {m['branch']} - Cat: {m['category']} - CR: {m['closing_rank']} - Match: {r['match_percentage']:.1f}%")
