from dataclasses import dataclass
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass
class Result(Generic[T]):
    code: int = 0
    message: str = "success"
    data: T | None = None
    trace_id: str = ""

    @staticmethod
    def ok(data: T = None, message: str = "success", trace_id: str = "") -> "Result[T]":
        return Result(code=0, message=message, data=data, trace_id=trace_id)

    @staticmethod
    def fail(code: int = -1, message: str = "error", trace_id: str = "") -> "Result[Any]":
        return Result(code=code, message=message, data=None, trace_id=trace_id)

    @staticmethod
    def paginate(items: list, total: int, page: int, page_size: int, trace_id: str = "") -> "Result[dict]":
        return Result(
            code=0,
            message="success",
            data={
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "pages": (total + page_size - 1) // page_size if page_size > 0 else 0,
            },
            trace_id=trace_id,
        )


class BizException(Exception):
    def __init__(self, code: int = -1, message: str = "Business error", detail: str = ""):
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(message)


class NotFoundException(BizException):
    def __init__(self, message: str = "Resource not found", detail: str = ""):
        super().__init__(code=404, message=message, detail=detail)


class ForbiddenException(BizException):
    def __init__(self, message: str = "Forbidden", detail: str = ""):
        super().__init__(code=403, message=message, detail=detail)


class UnauthorizedException(BizException):
    def __init__(self, message: str = "Unauthorized", detail: str = ""):
        super().__init__(code=401, message=message, detail=detail)


class ValidationException(BizException):
    def __init__(self, message: str = "Validation error", detail: str = ""):
        super().__init__(code=422, message=message, detail=detail)


class ConflictException(BizException):
    def __init__(self, message: str = "Conflict", detail: str = ""):
        super().__init__(code=409, message=message, detail=detail)


class DuplicateCodeException(BizException):
    def __init__(self, message: str = "Duplicate code", detail: str = ""):
        super().__init__(code=4091, message=message, detail=detail)


class TenantMismatchException(BizException):
    def __init__(self, message: str = "Tenant mismatch", detail: str = ""):
        super().__init__(code=1001, message=message, detail=detail)


class IdempotencyConflictException(BizException):
    def __init__(self, message: str = "Duplicate request", detail: str = ""):
        super().__init__(code=1002, message=message, detail=detail)


class ExternalSystemException(BizException):
    def __init__(self, message: str = "External system unavailable", detail: str = ""):
        super().__init__(code=1003, message=message, detail=detail)


ERROR_CODE_MAP: dict[int, str] = {
    0: "success",
    -1: "unknown_error",
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    500: "internal_error",
    1001: "tenant_mismatch",
    1002: "idempotency_conflict",
    1003: "external_system_unavailable",
    1004: "state_illegal",
    1005: "permission_denied",
}
