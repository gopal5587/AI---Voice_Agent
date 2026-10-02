import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import agent, kb, realtime, vapi
from .config import settings
from .retrieval.index import get_index

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="Darwix AI Assessment", version="1.0.0")
_deployed = settings.public_base_url.startswith("https://")
if _deployed:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins
        + ["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_origin_regex=r"https://([a-z0-9-]+\.)*pages\.dev$",
        allow_methods=["*"],
        allow_headers=["*"],
    )
for module in (kb, agent, vapi, realtime):
    app.include_router(module.router)


@app.on_event("startup")
def warm() -> None:
    get_index()


@app.get("/api/health")
def health():
    idx = get_index()
    return {"status": "ok", "kb_version": idx.records[0]["kb_version"] if idx.records else None, "records": len(idx.records)}


@app.get("/api/config")
def public_config():
    return {
        "vapi_public_key": settings.vapi_public_key or None,
        "vapi_assistants": {k: v for k, v in settings.vapi_assistants.items() if v},
        "llm_enabled": settings.llm_enabled,
        "embedder": get_index().embedder.name,
        "asr_provider": settings.asr_provider if settings.asr_provider != "deepgram" or settings.deepgram_api_key else "vosk",
        "retrieval_min_score": settings.retrieval_min_score,
    }
