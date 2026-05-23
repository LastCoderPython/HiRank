from pydantic_settings import BaseSettings
from typing import Optional, List
from functools import lru_cache


class Settings(BaseSettings):
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True
    
    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,http://127.0.0.1:3001"
    
    # LLM Configuration
    llm_provider: str = "groq"
    groq_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    
    # Model Configuration
    primary_model: str = "llama-3.3-70b-versatile"
    fallback_model_1: str = "llama-3.1-8b-instant"
    fallback_model_2: str = "llama-3.1-8b-instant"
    
    # Embedding Configuration
    embedding_provider: str = "huggingface"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    
    # Vector Database
    vector_db: str = "chroma"
    chroma_persist_dir: str = "./data/chroma"
    qdrant_url: str = "http://localhost:6333"
    
    # Data Paths
    cee_data_path: str = "./data/cee_cutoffs.csv"
    jee_data_path: str = "./data/jee_cutoffs.csv"
    
    # RAG Configuration
    chunk_size: int = 500
    chunk_overlap: int = 50
    retrieval_top_k: int = 10
    
    # Rank Buffer (for searching)
    rank_buffer_low: int = 200
    rank_buffer_high: int = 500
    
    # Supabase Configuration
    supabase_url: Optional[str] = None
    supabase_service_key: Optional[str] = None
    supabase_anon_key: Optional[str] = None
    supabase_jwt_secret: Optional[str] = None
    
    # Frontend URL for redirects
    frontend_url: str = "http://localhost:3000"

    # Agent Platform
    enable_agent_routes: bool = True
    agent_default_collection: str = "cee"
    agent_api_keys: Optional[str] = None
    agent_rate_limit_per_minute: int = 120

    # Observability
    observability_log_level: str = "INFO"

    # Redis (Celery broker + result backend + cache)
    redis_url: str = "redis://localhost:6379/0"

    # Gunicorn
    gunicorn_workers: int = 4

    # Tavily (Live Web Search Fallback)
    tavily_api_key: Optional[str] = None
    tavily_max_results: int = 5
    fallback_enabled: bool = True
    official_domain_suffixes: str = ".ac.in,.edu.in,.gov.in,.nic.in"
    
    # Model fallback order
    @property
    def model_order(self) -> List[str]:
        return [self.primary_model, self.fallback_model_1, self.fallback_model_2]

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
