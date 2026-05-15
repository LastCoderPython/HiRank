from typing import List, Dict, Any
from app.core.chroma_client import chroma_client
from app.models.requests import ParsedQuery
from app.config import settings


class Retriever:
    def __init__(self):
        self.chroma = chroma_client
    
    def retrieve(self, parsed_query: ParsedQuery, max_results: int = 10) -> List[Dict[str, Any]]:
        if parsed_query.rank is None:
            return self._semantic_search(parsed_query.raw_query, max_results)
        
        return self._rank_based_search(
            rank=parsed_query.rank,
            category=parsed_query.category,
            exam=parsed_query.exam or "CEE",
            branch=parsed_query.branch,
            max_results=max_results
        )
    
    def retrieve_multi_exam(self, parsed_queries: List[ParsedQuery], max_results_per_exam: int = 10) -> Dict[str, List[Dict[str, Any]]]:
        results = {}
        for pq in parsed_queries:
            exam = pq.exam or "CEE"
            if pq.rank:
                results[exam] = self._rank_based_search(
                    rank=pq.rank,
                    category=pq.category,
                    exam=exam,
                    branch=pq.branch,
                    max_results=max_results_per_exam
                )
        return results
    
    def _rank_based_search(
        self,
        rank: int,
        category: str,
        exam: str,
        branch: str = None,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        collection_name = "cee" if exam == "CEE" else "jee"
        
        buffer_low = settings.rank_buffer_low
        buffer_high = settings.rank_buffer_high
        
        base_results = self.chroma.query_by_rank(
            rank=rank,
            category=category,
            buffer_low=buffer_low,
            buffer_high=buffer_high,
            collection_name=collection_name,
            n_results=max_results * 2
        )
        
        if branch:
            filtered_results = [
                r for r in base_results
                if branch.lower() in r["metadata"].get("branch", "").lower()
            ]
            if len(filtered_results) >= max_results // 2:
                return filtered_results[:max_results]
        
        return base_results[:max_results]
    
    def _semantic_search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['hi', 'hello', 'hey', 'good morning', 'good evening']):
            return []
        
        if 'computer science' in query_lower or 'cse' in query_lower:
            return self._rank_based_search(500, "General", "CEE", "Computer Science", max_results)
        elif 'mechanical' in query_lower:
            return self._rank_based_search(500, "General", "CEE", "Mechanical", max_results)
        elif 'civil' in query_lower:
            return self._rank_based_search(500, "General", "CEE", "Civil", max_results)
        elif 'electrical' in query_lower:
            return self._rank_based_search(500, "General", "CEE", "Electrical", max_results)
        elif 'electronics' in query_lower:
            return self._rank_based_search(500, "General", "CEE", "Electronics", max_results)
        
        results = self.chroma.search_similar(
            query=query,
            collection_name="cee",
            n_results=max_results
        )
        return results
    
    def retrieve_college_info(
        self,
        college_name: str,
        exam: str = "CEE"
    ) -> List[Dict[str, Any]]:
        collection_name = "cee" if exam == "CEE" else "jee"
        
        return self.chroma.search_similar(
            query=f"Information about {college_name}",
            collection_name=collection_name,
            n_results=5,
            where_filter={"college_name": {"$contains": college_name}}
        )
    
    def get_match_statistics(
        self,
        user_rank: int,
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if not results:
            return {"total": 0, "high_match": 0, "moderate_match": 0, "low_match": 0}
        
        high_match = sum(1 for r in results if r["match_percentage"] >= 80)
        moderate_match = sum(1 for r in results if 60 <= r["match_percentage"] < 80)
        low_match = sum(1 for r in results if r["match_percentage"] < 60)
        
        return {
            "total": len(results),
            "high_match": high_match,
            "moderate_match": moderate_match,
            "low_match": low_match,
            "best_match": results[0] if results else None
        }


retriever = Retriever()
