from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = PROJECT_ROOT / "storage"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", validate_default=True)

    # App
    app_name: str = "SecondBrain"
    app_version: str = "0.1.0"
    debug: bool = True

    # Storage. Defaults are absolute so local behavior is independent of CWD.
    data_dir: Path = DEFAULT_DATA_DIR
    upload_dir: Path = DEFAULT_DATA_DIR / "uploads"
    chroma_dir: Path = DEFAULT_DATA_DIR / "chroma_db"
    sessions_dir: Path = DEFAULT_DATA_DIR / "sessions"
    graph_dir: Path = DEFAULT_DATA_DIR / "graph"
    temp_audio_dir: Path = DEFAULT_DATA_DIR / "temp_audio"
    chroma_collection: str = "second_brain"

    # API safety
    max_upload_size_bytes: int = 10 * 1024 * 1024
    max_remote_response_bytes: int = 2 * 1024 * 1024
    remote_request_timeout_seconds: int = 8
    max_graph_depth: int = 2
    cors_allowed_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:5173,http://127.0.0.1:5173"
    )

    # Database. Phase 2.1 intentionally does not provide a fallback database.
    # Configure DATABASE_URL explicitly before adding database-backed endpoints.
    database_url: str | None = None

    # AI
    embedding_model: str = "BAAI/bge-m3"
    max_chunk_size: int = 500
    chunk_overlap: int = 50
    default_top_k: int = 5
    gemini_api_key: str = ""
    groq_api_key: str = ""

    @field_validator(
        "data_dir",
        "upload_dir",
        "chroma_dir",
        "sessions_dir",
        "graph_dir",
        "temp_audio_dir",
        mode="after",
    )
    @classmethod
    def resolve_data_path(cls, value: Path) -> Path:
        return value if value.is_absolute() else PROJECT_ROOT / value

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


settings = Settings()

for runtime_dir in (
    settings.data_dir,
    settings.upload_dir,
    settings.chroma_dir,
    settings.sessions_dir,
    settings.graph_dir,
    settings.temp_audio_dir,
):
    runtime_dir.mkdir(parents=True, exist_ok=True)
