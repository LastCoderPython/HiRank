import asyncio
import threading
from langchain_huggingface import HuggingFaceEmbeddings
from app.config import settings
from typing import List
import numpy as np
import logging

logger = logging.getLogger(__name__)


class EmbeddingService:
    _instance: 'EmbeddingService' = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            cls._instance._lock = threading.Lock()
        return cls._instance
    
    def __init__(self):
        pass
    
    def _ensure_initialized(self):
        """Eagerly initialize the embedding model. Double-checked locking."""
        if self._initialized:
            return
        with self._lock:
            if self._initialized:
                return
            self._initialize_embeddings()
            self._initialized = True
    
    def _initialize_embeddings(self):
        try:
            self.embeddings = HuggingFaceEmbeddings(
                model_name=settings.embedding_model,
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )
            logger.info(f"Initialized embeddings: {settings.embedding_model}")
        except Exception as e:
            logger.error(f"Failed to initialize embeddings: {e}")
            raise
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        self._ensure_initialized()
        return self.embeddings.embed_documents(texts)
    
    def embed_query(self, text: str) -> List[float]:
        self._ensure_initialized()
        return self.embeddings.embed_query(text)
    
    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        self._ensure_initialized()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.embeddings.embed_documents, texts)
    
    async def aembed_query(self, text: str) -> List[float]:
        self._ensure_initialized()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.embeddings.embed_query, text)
    
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        vec1_np = np.array(vec1)
        vec2_np = np.array(vec2)
        return np.dot(vec1_np, vec2_np) / (np.linalg.norm(vec1_np) * np.linalg.norm(vec2_np))
        
    def embed_documents_in_batches(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        self._ensure_initialized()
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i: i + batch_size]
            embeddings = self.embed_documents(batch)
            all_embeddings.extend(embeddings)
            logger.info("Embedded batch %d-%d / %d", i, min(i + batch_size, len(texts)), len(texts))
        return all_embeddings


embedding_service = EmbeddingService()
