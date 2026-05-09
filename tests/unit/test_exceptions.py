from erp.shared.exceptions import (
    BizException,
    ExternalSystemException,
    IdempotencyConflictException,
    NotFoundException,
    Result,
    TenantMismatchException,
)


def test_result_ok():
    r = Result.ok(data={"key": "value"}, message="success", trace_id="t1")
    assert r.code == 0
    assert r.message == "success"
    assert r.data == {"key": "value"}
    assert r.trace_id == "t1"


def test_result_fail():
    r = Result.fail(code=-1, message="error", trace_id="t2")
    assert r.code == -1
    assert r.data is None


def test_result_paginate():
    r = Result.paginate(items=[1, 2], total=10, page=1, page_size=5, trace_id="t3")
    assert r.data["total"] == 10
    assert r.data["pages"] == 2


def test_biz_exception():
    exc = BizException(code=500, message="test error")
    assert exc.code == 500
    assert str(exc) == "test error"


def test_not_found_exception():
    exc = NotFoundException(detail="order not found")
    assert exc.code == 404


def test_tenant_mismatch_exception():
    exc = TenantMismatchException()
    assert exc.code == 1001


def test_idempotency_conflict_exception():
    exc = IdempotencyConflictException()
    assert exc.code == 1002


def test_external_system_exception():
    exc = ExternalSystemException()
    assert exc.code == 1003
