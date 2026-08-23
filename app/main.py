import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import auth, chat, search, upload
from app.core.config import settings
from app.core.exceptions import (
    AppError,
    EmbeddingFailedException,
    OCRFailedException,
    SecondBrainException,
    StorageException,
    UnsupportedFileTypeException,
)
from app.services.ownership_service import OwnershipMismatchError, OwnershipResourceNotFoundError
from app.models.api import ErrorResponse


logger = logging.getLogger(__name__)


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=ErrorResponse(error={"code": code, "message": message}).model_dump())


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Services remain lightweight at import/startup. The embedding model warms lazily on first use.
    from app.services.embedding_service import embedding_service
    from app.services.llm_service import llm_service
    from app.services.session_service import session_service
    from app.services.storage_service import storage_service

    app.state.embedding_service = embedding_service
    app.state.storage_service = storage_service
    app.state.llm_service = llm_service
    app.state.session_service = session_service
    try:
        yield
    finally:
        # Phase 2.1 only disposes an already-created pool. It does not connect
        # to PostgreSQL or create tables during application startup.
        from app.db.session import close_database

        close_database()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered Personal Memory Assistant",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "Idempotency-Key"],
)


@app.exception_handler(AppError)
async def handle_app_error(_: Request, exc: AppError):
    return error_response(exc.status_code, exc.code, exc.message)


async def ownership_not_found_response(_: Request, __: Exception):
    return error_response(404, "resource_not_found", "Resource was not found.")


app.add_exception_handler(OwnershipMismatchError, ownership_not_found_response)
app.add_exception_handler(OwnershipResourceNotFoundError, ownership_not_found_response)


@app.exception_handler(UnsupportedFileTypeException)
async def handle_file_type_error(_: Request, __: UnsupportedFileTypeException):
    return error_response(415, "unsupported_file_type", "The uploaded file type is not supported.")


@app.exception_handler(OCRFailedException)
async def handle_ocr_error(_: Request, __: OCRFailedException):
    return error_response(422, "ocr_failed", "Text could not be extracted from the uploaded file.")


async def dependency_error_response(exc: SecondBrainException):
    logger.exception("Dependency failure", exc_info=exc)
    return error_response(503, "dependency_unavailable", "A required processing dependency is temporarily unavailable.")


@app.exception_handler(StorageException)
async def handle_storage_error(_: Request, exc: StorageException):
    return await dependency_error_response(exc)


@app.exception_handler(EmbeddingFailedException)
async def handle_embedding_error(_: Request, exc: EmbeddingFailedException):
    return await dependency_error_response(exc)


@app.exception_handler(RequestValidationError)
async def handle_validation_error(_: Request, __: RequestValidationError):
    return error_response(422, "validation_error", "The request payload is invalid.")


@app.exception_handler(HTTPException)
async def handle_http_error(_: Request, exc: HTTPException):
    return error_response(exc.status_code, "http_error", "The request could not be completed.")


@app.exception_handler(Exception)
async def handle_unexpected_error(_: Request, exc: Exception):
    logger.exception("Unhandled application error", exc_info=exc)
    return error_response(500, "internal_error", "An unexpected server error occurred.")


app.include_router(upload.router, prefix="/api/v1", tags=["Upload"])
app.include_router(search.router, prefix="/api/v1", tags=["Search"])
app.include_router(chat.router, prefix="/api/v1", tags=["Chat"])
app.include_router(auth.router, prefix="/api/v1", tags=["Authentication"])


@app.get("/")
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "upload": "/api/v1/upload",
            "search": "/api/v1/search",
            "chat": "/api/v1/chat",
            "sessions": "/api/v1/sessions",
        },
    }


@app.get("/health")
def health():
    return {"status": "ok"}
