import logging

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List, Any
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    debug: bool = False
    runtime_env: str = "development"

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,http://127.0.0.1:3001"

    # LLM Provider
    llm_provider: str = "groq"
    groq_api_key: Optional[str] = None

    # Model Names
    primary_model: str = "llama-3.3-70b-versatile"
    fallback_model_1: str = "llama-3.1-8b-instant"
    fallback_model_2: str = "llama-3.1-8b-instant"

    # Embedding
    embedding_provider: str = "huggingface"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    huggingface_api_token: Optional[str] = None

    # Vector Database
    vector_db: str = "chroma"
    chroma_persist_dir: str = "./data/chroma"
    chroma_host: str = "chromadb"
    chroma_port: int = 8000
    chroma_auth_token: Optional[str] = None

    # Data CSV Paths
    cee_data_path: str = "./data/cee_cutoffs.csv"
    jee_data_path: str = "./data/jee_cutoffs.csv"

    # Supabase
    supabase_url: Optional[str] = None
    supabase_service_key: Optional[str] = None
    supabase_anon_key: Optional[str] = None
    supabase_jwt_secret: Optional[str] = None

    # Frontend URL for redirects
    frontend_url: str = "http://localhost:3000"

    @classmethod
    def validate_cors(cls, v: str) -> str:
        if not v.strip():
            logging.warning("CORS_ORIGINS is empty — all cross-origin requests will be blocked")
        return v

    _validate_cors = field_validator("cors_origins")(validate_cors)

    # Agent API
    agent_api_keys: Optional[str] = None
    agent_rate_limit_per_minute: int = 120

    # Celery / Redis broker
    redis_url: str = "redis://localhost:6379/0"

    # Backend URL (used for OAuth redirect_uri — never derive from Host header)
    backend_url: str = "http://localhost"

    # Tavily (Live Web Search)
    tavily_api_key: Optional[str] = None
    tavily_max_results: int = 5
    fallback_enabled: bool = True
    official_domain_suffixes: str = ".ac.in,.edu.in,.gov.in,.nic.in"

    # Freemium Usage Limits
    anon_prompt_limit: int = 3
    anon_tavily_limit: int = 1
    auth_tavily_monthly_limit: int = 5
    tavily_monthly_quota: int = 1000

    # Model fallback order
    @property
    def model_order(self) -> List[str]:
        return [self.primary_model, self.fallback_model_1, self.fallback_model_2]

    @model_validator(mode='before')
    @classmethod
    def replace_not_set(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for k, v in data.items():
                if v == "NOT_SET":
                    data[k] = None
        return data

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
