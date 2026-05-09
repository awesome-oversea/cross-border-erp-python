"""
数据导入兜底能力 (P5-017)

支持手工导入: 订单、账单、库存、物流轨迹
通过模板文件(CSV/Excel)批量导入，含字段映射与校验
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ImportTemplate:
    name: str = ""
    fields: list[dict] = field(default_factory=list)
    required_fields: list[str] = field(default_factory=list)
    field_mappings: dict[str, str] = field(default_factory=dict)
    validate_rules: dict[str, str] = field(default_factory=dict)


# 四类预置导入模板: 订单/库存/账单/物流轨迹
IMPORT_TEMPLATES = {
    "orders": ImportTemplate(
        name="订单导入",
        fields=[
            {"key": "platform_order_id", "label": "平台订单ID", "type": "string"},
            {"key": "platform", "label": "平台", "type": "string"},
            {"key": "order_date", "label": "下单时间", "type": "datetime"},
            {"key": "total_amount", "label": "订单金额", "type": "float"},
            {"key": "currency", "label": "币种", "type": "string"},
            {"key": "buyer_name", "label": "买家姓名", "type": "string"},
            {"key": "status", "label": "订单状态", "type": "string"},
        ],
        required_fields=["platform_order_id", "platform", "total_amount"],
    ),
    "inventory": ImportTemplate(
        name="库存导入",
        fields=[
            {"key": "sku", "label": "SKU编码", "type": "string"},
            {"key": "warehouse_code", "label": "仓库编码", "type": "string"},
            {"key": "qty_on_hand", "label": "在手数量", "type": "int"},
            {"key": "qty_available", "label": "可用数量", "type": "int"},
        ],
        required_fields=["sku", "warehouse_code", "qty_on_hand"],
    ),
    "bills": ImportTemplate(
        name="账单导入",
        fields=[
            {"key": "platform", "label": "平台", "type": "string"},
            {"key": "bill_no", "label": "账单编号", "type": "string"},
            {"key": "bill_type", "label": "账单类型", "type": "string"},
            {"key": "amount", "label": "金额", "type": "float"},
            {"key": "currency", "label": "币种", "type": "string"},
            {"key": "period", "label": "账期", "type": "string"},
        ],
        required_fields=["platform", "bill_no", "amount"],
    ),
    "tracking": ImportTemplate(
        name="物流轨迹导入",
        fields=[
            {"key": "tracking_no", "label": "追踪号", "type": "string"},
            {"key": "carrier", "label": "物流商", "type": "string"},
            {"key": "event_time", "label": "事件时间", "type": "datetime"},
            {"key": "event_location", "label": "事件地点", "type": "string"},
            {"key": "event_status", "label": "事件状态", "type": "string"},
        ],
        required_fields=["tracking_no", "carrier", "event_status"],
    ),
}


class ImportService:
    """手工导入服务: CSV解析、字段映射、校验、转换"""
    """手工导入服务: CSV解析、字段映射、校验、转换"""

    @staticmethod
    def get_template(template_type: str) -> ImportTemplate | None:
        return IMPORT_TEMPLATES.get(template_type)

    @staticmethod
    def list_templates() -> list[dict]:
        return [{"type": k, "name": v.name, "fields": len(v.fields)} for k, v in IMPORT_TEMPLATES.items()]

    @staticmethod
    def parse_csv(content: str, template_type: str) -> dict:
        """解析CSV并校验"""
        template = IMPORT_TEMPLATES.get(template_type)
        if not template:
            return {"success": False, "error": f"不支持的导入类型: {template_type}", "rows": 0}

        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
        if not rows:
            return {"success": False, "error": "CSV文件为空", "rows": 0}

        errors = []
        valid_rows = []
        for i, row in enumerate(rows, 2):
            row_errors = ImportService._validate_row(row, template)
            if row_errors:
                errors.extend([f"第{i}行: {e}" for e in row_errors])
            else:
                converted = ImportService._convert_row(row, template)
                valid_rows.append(converted)

        return {
            "success": len(errors) == 0,
            "total": len(rows),
            "valid": len(valid_rows),
            "error_count": len(errors),
            "errors": errors[:50],
            "rows": valid_rows,
        }

    @staticmethod
    def _validate_row(row: dict, template: ImportTemplate) -> list[str]:
        e = []
        for rf in template.required_fields:
            if not row.get(rf, "").strip():
                e.append(f"缺少必填字段: {rf}")
        for f in template.fields:
            val = row.get(f["key"], "").strip()
            if val:
                try:
                    if f["type"] == "float": float(val)
                    elif f["type"] == "int": int(val)
                except ValueError:
                    e.append(f"字段'{f['key']}'值'{val}'格式不正确，期望{f['type']}")
        return e

    @staticmethod
    def _convert_row(row: dict, template: ImportTemplate) -> dict:
        converted = {}
        for f in template.fields:
            val = row.get(f["key"], "").strip()
            if val:
                try:
                    if f["type"] == "float": val = float(val)
                    elif f["type"] == "int": val = int(val)
                except ValueError: pass
            converted[f["key"]] = val
        return converted
