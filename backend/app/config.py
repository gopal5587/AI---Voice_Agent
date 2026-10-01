import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(os.getenv("PROJECT_ROOT", Path(__file__).resolve().parents[2]))
load_dotenv(ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


@dataclass(frozen=True)
class Settings:
    root: Path = ROOT
    raw_dir: Path = ROOT / "data" / "raw"
    processed_dir: Path = ROOT / "data" / "processed"
    runtime_dir: Path = ROOT / "data" / "runtime"
    scenarios_dir: Path = ROOT / "data" / "scenarios"
    configs_dir: Path = ROOT / "configs"
    evidence_dir: Path = ROOT / "evidence"

    public_base_url: str = _env("PUBLIC_BASE_URL", "http://localhost:8000")
    cors_origins: list[str] = field(
        default_factory=lambda: [o for o in _env("CORS_ORIGINS", "http://localhost:5173").split(",") if o]
    )
    webhook_secret: str = _env("WEBHOOK_SECRET")

    embedding_provider: str = _env("EMBEDDING_PROVIDER", "local")
    qdrant_url: str = _env("QDRANT_URL")
    retrieval_min_score: float = float(_env("RETRIEVAL_MIN_SCORE", "0.40"))

    openai_api_key: str = _env("OPENAI_API_KEY")
    openai_model: str = _env("OPENAI_MODEL", "gpt-4o-mini")
    openai_embedding_model: str = _env("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    vapi_api_key: str = _env("VAPI_API_KEY")
    vapi_public_key: str = _env("VAPI_PUBLIC_KEY")
    vapi_assistants: dict[str, str] = field(
        default_factory=lambda: {
            "business_loan": _env("VAPI_ASSISTANT_BUSINESS_LOAN"),
            "ph_life_insurance": _env("VAPI_ASSISTANT_PH"),
            "id_consumer_finance": _env("VAPI_ASSISTANT_ID"),
        }
    )

    asr_provider: str = _env("ASR_PROVIDER", "vosk")
    deepgram_api_key: str = _env("DEEPGRAM_API_KEY")
    vosk_model_path: Path = ROOT / _env("VOSK_MODEL_PATH", "models/vosk-model-small-en-us-0.15")

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key)


settings = Settings()
