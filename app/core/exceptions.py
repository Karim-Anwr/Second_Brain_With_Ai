class SecondBrainException(Exception):
    pass

class OCRFailedException(SecondBrainException):
    pass

class UnsupportedFileTypeException(SecondBrainException):
    pass

class EmbeddingFailedException(SecondBrainException):
    pass

class DocumentNotFoundException(SecondBrainException):
    pass

class StorageException(SecondBrainException):
    pass
