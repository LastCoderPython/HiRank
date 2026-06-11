import threading
import chromadb
from chromadb.config import Settings as ChromaSettings
from app.config import settings
from typing import List, Dict, Any, Optional
from app.core.embeddings import embedding_service


class ChromaClient:
    _instance: 'ChromaClient' = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            cls._instance._lock = threading.Lock()
        return cls._instance
    
    def __init__(self):
        pass

    def _ensure_initialized(self):
        """Eagerly initialize ChromaDB client and collections. Double-checked locking."""
        if self._initialized:
            return
        with self._lock:
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
            self.college_web_docs_collection = self._get_or_create_collection("college_web_docs")
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
        self._ensure_initialized()

        collection = self.cee_collection if collection_name == "cee" else self.jee_collection
        
        embeddings = embedding_service.embed_documents(documents)
        
        collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
    
    def search_similar(
        self,
        query: str,
        collection_name: str = "cee",
        n_results: int = 5,
        where_filter: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        self._ensure_initialized()

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
    
    def get_collection(self, name: str = "college_web_docs"):
        self._ensure_initialized()
        if name == "cee":
            return self.cee_collection
        elif name == "jee":
            return self.jee_collection
        elif name == "college_web_docs":
            return self.college_web_docs_collection
        return self.client.get_or_create_collection(name)

    def inspect_metadata(self, collection_name: str = "college_web_docs") -> Dict[str, Any]:
        self._ensure_initialized()
        collection = self.get_collection(collection_name)
        records = collection.get(include=["metadatas"])
        metas = records["metadatas"] or []

        college_names = set()
        page_types = set()
        validation_statuses = set()
        domains = set()
        null_college = 0
        null_page_type = 0

        for m in metas:
            cn = (m.get("college_name") or "").strip().upper()
            if cn:
                college_names.add(cn)
            else:
                null_college += 1
            pt = (m.get("page_type") or "").strip()
            if pt:
                page_types.add(pt)
            else:
                null_page_type += 1
            vs = m.get("validation_status", "unknown")
            validation_statuses.add(vs)
            dom = m.get("domain", "")
            if dom:
                domains.add(dom)

        return {
            "total_docs": len(metas),
            "unique_colleges": sorted(college_names),
            "unique_page_types": sorted(page_types),
            "validation_statuses": sorted(validation_statuses),
            "domains": sorted(domains),
            "null_college_name": null_college,
            "null_page_type": null_page_type,
        }

    def get_all_colleges(self, collection_name: str = "cee") -> List[str]:
        self._ensure_initialized()
        collection = self.cee_collection if collection_name == "cee" else self.jee_collection
        results = collection.get()
        
        colleges = set()
        for metadata in results["metadatas"]:
            colleges.add(metadata.get("college_name", "") or metadata.get("institute_name", ""))
        
        return list(colleges)
    
    def count_documents(self, collection_name: str = "cee") -> int:
        self._ensure_initialized()
        collection = self.cee_collection if collection_name == "cee" else self.jee_collection
        return collection.count()
    
    def reset_collection(self, collection_name: str = "cee"):
        self._ensure_initialized()
        collection = self.cee_collection if collection_name == "cee" else self.jee_collection
        self.client.delete_collection(collection_name)
        if collection_name == "cee":
            self.cee_collection = self._get_or_create_collection("cee")
        else:
            self.jee_collection = self._get_or_create_collection("jee")


chroma_client = ChromaClient()
