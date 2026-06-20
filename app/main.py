from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import upload, search, chat
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(" جاري تحميل الـ models...")

    from app.services.embedding_service import embedding_service
    print(" Embedding model جاهز")

    from app.services.storage_service import storage_service
    print(" ChromaDB جاهز")

    from app.services.llm_service import llm_service
    print(" LLM جاهز")

    from app.services.session_service import session_service
    print(" Session Service جاهز")

    print(" الـ App جاهز!")
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered Personal Memory Assistant",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ──
app.include_router(
    upload.router,
    prefix="/api/v1",
    tags=["Upload"]
)
app.include_router(
    search.router,
    prefix="/api/v1",
    tags=["Search"]
)
app.include_router(
    chat.router,
    prefix="/api/v1",
    tags=["Chat"]  # ← جديد
)


@app.get("/")
def root():
    return {
        "app":     settings.app_name,
        "version": settings.app_version,
        "status":  "running ",
        "docs":    "/docs",
        "endpoints": {
            "upload":   "/api/v1/upload",
            "search":   "/api/v1/search",
            "chat":     "/api/v1/chat",
            "sessions": "/api/v1/sessions",
        }
    }


@app.get("/health")
def health():
    return {"status": "ok"}