from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: str = "groq"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"
    groq_model_math: str = "llama-3.3-70b-versatile"

    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "llama3.2"
    llm_api_key: str = "ollama"

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chunk_size: int = 700
    chunk_overlap: int = 120
    top_k: int = 5
    math_top_k: int = 12
    max_upload_mb: int = 15
    upload_dir: Path = Path("uploads")
    vector_dir: Path = Path("vectorstore")
    database_path: Path = Path("data/app.db")
    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = 60 * 24 * 7
    ocr_enabled: bool = True


settings = Settings()
