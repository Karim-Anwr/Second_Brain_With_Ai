from app.services.ocr_service import ocr_service
from app.services.embedding_service import embedding_service
from app.services.storage_service import get_storage_service as _get_storage_service


def get_ocr_service():
    return ocr_service


def get_embedding_service():
    return embedding_service


def get_storage_service():
    return _get_storage_service()
