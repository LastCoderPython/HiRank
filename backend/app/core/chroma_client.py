import chromadb
from chromadb.config import Settings as ChromaSettings
from app.config import settings
from typing import List, Dict, Any, Optional
from app.core.embeddings import embedding_service
import json


class ChromaClient:
    _instance: 'ChromaClient' = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        self.cee_collection = self._get_or_create_collection("cee")
        self.jee_collection = self._get_or_create_collection("jee")
        self._initialized = True
    
    def _get_or_create_collection(self, name: str):
        return self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"}
        )
    
    def add_documents(
        self,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
        collection_name: str = "cee"
    ):
        collection = self.cee_collection if collection_name == "cee" else self.jee_collection
        
        embeddings = embedding_service.embed_documents(documents)
        
        collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
    
    def query_by_rank(
        self,
        rank: int,
        category: str = "General",
        buffer_low: int = 200,
        buffer_high: int = 500,
        collection_name: str = "cee",
        n_results: int = 10
    ) -> List[Dict[str, Any]]:
        collection = self.cee_collection if collection_name == "cee" else self.jee_collection
        
        results = collection.get(limit=5000)
        
        formatted_results = []
        for i, doc in enumerate(results["documents"]):
            metadata = results["metadatas"][i]
            
            doc_category = metadata.get("category", "General")
            closing_rank = metadata.get("closing_rank", 0)
            
            try:
                closing_rank = int(closing_rank) if closing_rank else 0
            except:
                closing_rank = 0
            
            if closing_rank <= 0:
                continue
            
            if rank <= closing_rank:
                match_percentage = 100.0
            else:
                excess = rank - closing_rank
                buffer = min(500, closing_rank * 0.1)
                if excess <= buffer:
                    match_percentage = max(50, 100 - (excess / buffer) * 50)
                else:
                    match_percentage = max(0, 50 - (excess - buffer) / closing_rank * 50)
            
            formatted_results.append({
                "id": results["ids"][i],
                "document": doc,
                "metadata": metadata,
                "match_percentage": match_percentage
            })
        
        user_category_results = sorted(
            [r for r in formatted_results if r["metadata"].get("category") == category and r["match_percentage"] >= 50],
            key=lambda x: (x["match_percentage"], -x["metadata"].get("closing_rank", 0)),
            reverse=True
        )
        
        other_category_results = []
        for other_cat in ["OBC", "EWS", "General", "SC", "ST"]:
            if other_cat == category:
                continue
            cat_results = sorted(
                [r for r in formatted_results if r["metadata"].get("category") == other_cat and r["match_percentage"] >= 80],
                key=lambda x: (x["match_percentage"], -x["metadata"].get("closing_rank", 0)),
                reverse=True
            )
            for r in cat_results[:3]:
                if r not in other_category_results:
                    other_category_results.append(r)
        
        final_results = user_category_results[:n_results]
        
        for other in other_category_results:
            if len(final_results) >= n_results * 2:
                break
            final_results.append(other)
        
        return final_results[:n_results * 2]
    
    def search_similar(
        self,
        query: str,
        collection_name: str = "cee",
        n_results: int = 5,
        where_filter: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        collection = self.cee_collection if collection_name == "cee" else self.jee_collection
        
        query_embedding = embedding_service.embed_query(query)
        
        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": n_results * 2
        }
        
        if where_filter:
            kwargs["where"] = where_filter
        
        results = collection.query(**kwargs)
        
        formatted_results = []
        for i, doc in enumerate(results["documents"][0]):
            metadata = results["metadatas"][0][i]
            distance = results["distances"][0][i] if results["distances"] else 0
            
            match_percentage = max(0, min(100, (1 - distance) * 100)) if distance else 50.0
            
            formatted_results.append({
                "id": results["ids"][0][i],
                "document": doc,
                "metadata": metadata,
                "distance": distance,
                "match_percentage": match_percentage
            })
        
        return formatted_results[:n_results]
    
    def _calculate_match(self, user_rank: int, closing_rank: int) -> float:
        if user_rank <= closing_rank:
            return 100.0
        else:
            excess = user_rank - closing_rank
            buffer = 500
            if excess >= buffer:
                return max(0, 100 - (excess - buffer) / 10)
            return max(50, 100 - (excess / buffer) * 50)
    
    def get_all_colleges(self, collection_name: str = "cee") -> List[str]:
        collection = self.cee_collection if collection_name == "cee" else self.jee_collection
        results = collection.get()
        
        colleges = set()
        for metadata in results["metadatas"]:
            colleges.add(metadata.get("college_name", "") or metadata.get("institute_name", ""))
        
        return list(colleges)
    
    def count_documents(self, collection_name: str = "cee") -> int:
        collection = self.cee_collection if collection_name == "cee" else self.jee_collection
        return collection.count()
    
    def reset_collection(self, collection_name: str = "cee"):
        collection = self.cee_collection if collection_name == "cee" else self.jee_collection
        self.client.delete_collection(collection_name)
        if collection_name == "cee":
            self.cee_collection = self._get_or_create_collection("cee")
        else:
            self.jee_collection = self._get_or_create_collection("jee")


chroma_client = ChromaClient()
