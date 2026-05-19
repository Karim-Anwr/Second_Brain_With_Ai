from app.services.ocr_service import ocr_service
from app.services.embedding_service import embedding_service
from app.services.storage_service import storage_service

def get_ocr_service():
    return ocr_service

def get_embedding_service():
    return embedding_service

def get_storage_service():
    return storage_service