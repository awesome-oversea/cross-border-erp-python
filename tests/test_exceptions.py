from __future__ import annotations

import pytest

from erp.shared.exceptions import (
    ERROR_CODE_MAP,
    BizException,
    ForbiddenException,
    IdempotencyConflictException,
    NotFoundException,
    Result,
    TenantMismatchException,
    UnauthorizedException,
    ValidationException,
)


class TestResult:
    def test_ok(self):
        r = Result.ok(data={"id": "1"}, trace_id="t1")
        assert r.code == 0
        assert r.data == {"id": "1"}
        assert r.trace_id == "t1"

    def test_fail(self):
        r = Result.fail(code=422, message="bad param", trace_id="t2")
        assert r.code == 422
        assert r.message == "bad param"

    def test_paginate(self):
        r = Result.paginate(items=[1, 2], total=10, page=1, page_size=2, trace_id="t3")
        assert r.code == 0
        assert r.data["total"] == 10
        assert r.data["pages"] == 5


class TestBizException:
    def test_raise_and_catch(self):
        with pytest.raises(BizException) as exc_info:
            raise BizException(code=404, message="not found")
        assert exc_info.value.code == 404
        assert exc_info.value.message == "not found"

    def test_not_found_exception(self):
        with pytest.raises(NotFoundException):
            raise NotFoundException("resource missing")

    def test_forbidden_exception(self):
        with pytest.raises(ForbiddenException):
            raise ForbiddenException()

    def test_unauthorized_exception(self):
        with pytest.raises(UnauthorizedException):
            raise UnauthorizedException()

    def test_validation_exception(self):
        with pytest.raises(ValidationException):
            raise ValidationException("invalid input")

    def test_tenant_mismatch_exception(self):
        with pytest.raises(TenantMismatchException):
            raise TenantMismatchException()

    def test_idempotency_conflict_exception(self):
        with pytest.raises(IdempotencyConflictException):
            raise IdempotencyConflictException()


class TestErrorCodeMap:
    def test_error_codes_defined(self):
        assert 0 in ERROR_CODE_MAP
        assert 404 in ERROR_CODE_MAP
        assert 403 in ERROR_CODE_MAP
        assert 401 in ERROR_CODE_MAP
        assert 422 in ERROR_CODE_MAP
        assert 1001 in ERROR_CODE_MAP
        assert 1002 in ERROR_CODE_MAP
