from __future__ import annotations

ERROR_CODES: dict[str, dict[str, str]] = {
    "SUCCESS": {"code": 0, "en": "Success", "zh": "成功"},
    "UNKNOWN_ERROR": {"code": -1, "en": "Unknown error", "zh": "未知错误"},
    "BAD_REQUEST": {"code": 400, "en": "Bad request", "zh": "请求参数错误"},
    "UNAUTHORIZED": {"code": 401, "en": "Unauthorized", "zh": "未授权"},
    "FORBIDDEN": {"code": 403, "en": "Forbidden", "zh": "禁止访问"},
    "NOT_FOUND": {"code": 404, "en": "Resource not found", "zh": "资源不存在"},
    "CONFLICT": {"code": 409, "en": "Conflict", "zh": "冲突"},
    "VALIDATION_ERROR": {"code": 422, "en": "Validation error", "zh": "数据校验失败"},
    "INTERNAL_ERROR": {"code": 500, "en": "Internal server error", "zh": "服务器内部错误"},
    "TENANT_MISMATCH": {"code": 1001, "en": "Tenant mismatch", "zh": "租户不匹配"},
    "IDEMPOTENCY_CONFLICT": {"code": 1002, "en": "Duplicate request", "zh": "重复请求"},
    "EXTERNAL_SYSTEM_UNAVAILABLE": {"code": 1003, "en": "External system unavailable", "zh": "外部系统不可用"},
    "STATE_ILLEGAL": {"code": 1004, "en": "Illegal state transition", "zh": "非法状态转换"},
    "PERMISSION_DENIED": {"code": 1005, "en": "Permission denied", "zh": "权限不足"},
    "TENANT_SUSPENDED": {"code": 1006, "en": "Tenant suspended", "zh": "租户已停用"},
    "USER_LOCKED": {"code": 1007, "en": "User account locked", "zh": "用户账号已锁定"},
    "USER_DISABLED": {"code": 1008, "en": "User account disabled", "zh": "用户账号已禁用"},
    "PASSWORD_EXPIRED": {"code": 1009, "en": "Password expired", "zh": "密码已过期"},
    "TOKEN_EXPIRED": {"code": 1010, "en": "Token expired", "zh": "令牌已过期"},
    "TOKEN_INVALID": {"code": 1011, "en": "Invalid token", "zh": "无效令牌"},
    "ROLE_SYSTEM_PROTECTED": {"code": 1012, "en": "System role cannot be modified", "zh": "系统角色不可修改"},
    "DUPLICATE_CODE": {"code": 1013, "en": "Code already exists", "zh": "编码已存在"},
    "DUPLICATE_USERNAME": {"code": 1014, "en": "Username already exists", "zh": "用户名已存在"},
    "ORG_HAS_CHILDREN": {"code": 1015, "en": "Organization has children", "zh": "组织存在子节点"},
    "PMS_WRITE_FORBIDDEN": {"code": 2001, "en": "PMS cannot write formal business objects", "zh": "PMS不能写入正式业务终态"},
    "PMS_PERMISSION_DENIED": {"code": 2002, "en": "PMS permission denied", "zh": "PMS权限不足"},
    "PMS_APPROVAL_REQUIRED": {"code": 2003, "en": "PMS suggestion requires ERP approval", "zh": "PMS建议需要ERP审批"},
    "PMS_IDEMPOTENCY_REQUIRED": {"code": 2004, "en": "PMS write request requires idempotency key", "zh": "PMS写请求需要幂等键"},
    "RECOMMENDATION_ALREADY_EXISTS": {"code": 2010, "en": "Recommendation already exists", "zh": "建议已存在"},
    "RECOMMENDATION_INVALID_STATE": {"code": 2011, "en": "Recommendation state transition invalid", "zh": "建议状态转换无效"},
    "APPROVAL_FLOW_NOT_FOUND": {"code": 2020, "en": "Approval flow not found", "zh": "审批流程不存在"},
    "APPROVAL_ALREADY_PROCESSED": {"code": 2021, "en": "Approval already processed", "zh": "审批已处理"},
    "APPROVAL_NOT_ASSIGNED": {"code": 2022, "en": "Approval task not assigned to you", "zh": "审批任务未分配给您"},
    "SKU_NOT_FOUND": {"code": 3001, "en": "SKU not found", "zh": "SKU不存在"},
    "LISTING_NOT_FOUND": {"code": 3002, "en": "Listing not found", "zh": "Listing不存在"},
    "ORDER_NOT_FOUND": {"code": 3003, "en": "Order not found", "zh": "订单不存在"},
    "INSUFFICIENT_STOCK": {"code": 3004, "en": "Insufficient stock", "zh": "库存不足"},
    "PURCHASE_ORDER_NOT_FOUND": {"code": 3005, "en": "Purchase order not found", "zh": "采购单不存在"},
    "SUPPLIER_NOT_FOUND": {"code": 3006, "en": "Supplier not found", "zh": "供应商不存在"},
    "WAREHOUSE_NOT_FOUND": {"code": 3007, "en": "Warehouse not found", "zh": "仓库不存在"},
    "SHIPMENT_NOT_FOUND": {"code": 3008, "en": "Shipment not found", "zh": "物流单不存在"},
    "COST_EVENT_NOT_FOUND": {"code": 3009, "en": "Cost event not found", "zh": "成本事件不存在"},
    "FILE_TYPE_NOT_ALLOWED": {"code": 4001, "en": "File type not allowed", "zh": "文件类型不允许"},
    "FILE_SIZE_EXCEEDED": {"code": 4002, "en": "File size exceeded", "zh": "文件大小超限"},
    "RATE_LIMIT_EXCEEDED": {"code": 4003, "en": "Rate limit exceeded", "zh": "请求频率超限"},
    "CIRCUIT_BREAKER_OPEN": {"code": 4004, "en": "Circuit breaker open", "zh": "熔断器开启"},
}


def get_error_message(error_key: str, lang: str = "zh") -> str:
    entry = ERROR_CODES.get(error_key, {})
    return entry.get(lang, entry.get("en", error_key))


def get_error_code(error_key: str) -> int:
    entry = ERROR_CODES.get(error_key, {})
    return entry.get("code", -1)
