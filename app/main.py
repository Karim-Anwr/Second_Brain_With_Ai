from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import upload, search
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered Personal Memory Search Engine",
)

# ── CORS — مهم للـ Mobile App ──
# بيسمح للـ Flutter يكلم الـ API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Phase 2: حدد الـ origins
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

@app.get("/")
def root():
    return {
        "app":     settings.app_name,
        "version": settings.app_version,
        "status":  "running 🚀",
        "docs":    "/docs",
    }

@app.get("/health")
def health():
    return {"status": "ok"}