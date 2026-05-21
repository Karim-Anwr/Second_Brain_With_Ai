from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    # App
    app_name: str = "SecondBrain"
    app_version: str = "0.1.0"
    debug: bool = True

    # Storage
    upload_dir: str = "storage/uploads"
    chroma_dir: str = "storage/chroma_db"
    chroma_collection: str = "second_brain"

    # AI
    embedding_model: str = "BAAI/bge-m3" 
    max_chunk_size: int = 500
    chunk_overlap: int = 50
    default_top_k: int = 5
    
    gemini_api_key: str = ""
    groq_api_key: str = ""

    class Config:
        env_file = ".env"

# instance واحد بس — Singleton pattern
settings = Settings()

# إنشاء الـ folders لو مش موجودة
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
Path(settings.chroma_dir).mkdir(parents=True, exist_ok=True)