from fastapi import HTTPException, status
from typing import Optional, Any


class AppException(HTTPException):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Optional[Any] = None,
    ):
        super().__init__(
            status_code=status_code,
            detail={"code": code, "message": message, "details": details},
        )
        self.code = code
        self.message = message
        self.details = details


class NotFoundException(AppException):
    def __init__(self, message: str, code: str = "NOT_FOUND"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, code=code, message=message)


class InsufficientStockException(AppException):
    def __init__(self, message: str = "Tồn kho không đủ để đáp ứng yêu cầu"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INSUFFICIENT_STOCK",
            message=message,
        )


class ValidationException(AppException):
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="VALIDATION_ERROR",
            message=message,
            details=details,
        )


class ConflictException(AppException):
    def __init__(self, message: str):
        super().__init__(status_code=status.HTTP_409_CONFLICT, code="CONFLICT", message=message)
