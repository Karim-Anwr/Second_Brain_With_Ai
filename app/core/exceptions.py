class SecondBrainException(Exception):
    """Base exception for expected application failures."""


class AppError(SecondBrainException):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class ResourceNotFoundException(AppError):
    def __init__(self, resource: str = "Resource"):
        super().__init__("resource_not_found", f"{resource} was not found.", 404)


class InvalidRequestException(AppError):
    def __init__(self, message: str = "The request is invalid."):
        super().__init__("invalid_request", message, 400)


class AuthenticationFailedException(AppError):
    """Generic login failure that does not reveal account state."""

    def __init__(self):
        super().__init__("authentication_failed", "Invalid email or password.", 401)


class RegistrationFailedException(AppError):
    """Client-safe registration conflict without exposing database details."""

    def __init__(self):
        super().__init__("registration_failed", "Unable to create account.", 409)


class UploadTooLargeException(AppError):
    def __init__(self):
        super().__init__("upload_too_large", "The uploaded file exceeds the configured size limit.", 413)


class UnsafeURLError(AppError):
    def __init__(self, message: str = "The URL is not allowed."):
        super().__init__("unsafe_url", message, 400)


class StorageCorruptionException(AppError):
    def __init__(self, resource: str = "Stored data"):
        super().__init__("storage_corrupt", f"{resource} is corrupt and was not modified.", 409)


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
