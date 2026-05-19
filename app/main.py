from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import upload, search
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    بيشتغل مرة واحدة وقت الـ startup.
    بيحمل الـ models في الـ background.
    """
    print(" جاري تحميل الـ models...")
    
    # حمّل الـ embedding model
    from app.services.embedding_service import embedding_service
    print(" Embedding model جاهز")
    
    # حمّل الـ storage
    from app.services.storage_service import storage_service
    print(" ChromaDB جاهز")
    
    print(" الـ App جاهز!")
    
    yield  # هنا الـ app بيشتغل


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered Personal Memory Search Engine",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api/v1", tags=["Upload"])
app.include_router(search.router, prefix="/api/v1", tags=["Search"])

@app.get("/")
def root():
    return {
        "app":    settings.app_name,
        "status": "running ",
        "docs":   "/docs",
    }

@app.get("/health")
def health():
    return {"status": "ok"}