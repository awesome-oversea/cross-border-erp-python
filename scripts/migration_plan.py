from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone


class DataMigrationPlan:
    MIGRATION_PHASES = [
        {
            "phase": 1,
            "name": "基础主数据迁移",
            "tables": [
                "iam.tenant", "iam.organization", "iam.user", "iam.role",
                "iam.permission", "iam.user_role", "iam.role_permission",
            ],
            "order": 1,
            "strategy": "全量导出导入",
            "validation": "行数对比 + 关键字段抽样校验",
        },
        {
            "phase": 2,
            "name": "产品主数据迁移",
            "tables": [
                "pdm.category", "pdm.brand", "pdm.spu", "pdm.sku",
                "pdm.sku_variant", "pdm.channel_sku_mapping",
            ],
            "order": 2,
            "strategy": "全量导出导入 + 图片URL转换",
            "validation": "SPU/SKU编码唯一性 + 分类树完整性",
        },
        {
            "phase": 3,
            "name": "销售与店铺数据迁移",
            "tables": [
                "som.store", "som.listing", "som.price_rule",
                "sys.store_authorization",
            ],
            "order": 3,
            "strategy": "全量导出导入 + 授权Token重新加密",
            "validation": "店铺数量 + 授权状态校验",
        },
        {
            "phase": 4,
            "name": "供应链与仓储数据迁移",
            "tables": [
                "scm.supplier", "scm.purchase_order",
                "wms.warehouse", "wms.warehouse_area", "wms.location",
                "wms.inventory_account", "wms.inventory_transaction",
            ],
            "order": 4,
            "strategy": "全量导出导入 + 库存快照校验",
            "validation": "库存余额对比 + 库位映射校验",
        },
        {
            "phase": 5,
            "name": "订单与物流数据迁移",
            "tables": [
                "oms.sales_order", "oms.order_item", "oms.refund_order",
                "tms.shipment", "tms.tracking",
            ],
            "order": 5,
            "strategy": "增量迁移 + 状态映射",
            "validation": "订单金额汇总 + 状态分布校验",
        },
        {
            "phase": 6,
            "name": "财务数据迁移",
            "tables": [
                "fms.cost_event", "fms.payment", "fms.settlement",
                "fms.billing_strategy", "fms.voucher_template",
            ],
            "order": 6,
            "strategy": "全量导出导入 + 金额精度校验",
            "validation": "金额汇总对比 + 凭证平衡校验",
        },
    ]

    ROLLBACK_STRATEGY = {
        "method": "快照回滚",
        "steps": [
            "1. 迁移前对目标库做全量备份",
            "2. 每个Phase完成后记录checkpoint",
            "3. 回滚时恢复到最近checkpoint的备份",
            "4. 验证回滚后数据完整性",
        ],
    }

    VALIDATION_QUERIES = {
        "tenant_count": "SELECT COUNT(*) FROM iam.tenant",
        "user_count": "SELECT COUNT(*) FROM iam.user",
        "sku_count": "SELECT COUNT(*) FROM pdm.sku",
        "order_count": "SELECT COUNT(*) FROM oms.sales_order",
        "inventory_balance": "SELECT SUM(available_qty) FROM wms.inventory_account",
        "cost_event_sum": "SELECT SUM(amount) FROM fms.cost_event",
    }

    @classmethod
    def generate_migration_script(cls, phase: int, source_db: str, target_db: str) -> str:
        phase_data = cls.MIGRATION_PHASES[phase - 1]
        tables = phase_data["tables"]
        lines = [
            f"-- Phase {phase}: {phase_data['name']}",
            f"-- Source: {source_db}",
            f"-- Target: {target_db}",
            f"-- Strategy: {phase_data['strategy']}",
            f"-- Generated at: {datetime.now(timezone.utc).isoformat()}",
            "",
        ]
        for table in tables:
            schema, table_name = table.split(".")
            lines.extend([
                f"-- Migrate {schema}.{table_name}",
                f"INSERT INTO {target_db}.{schema}.{table_name}",
                f"SELECT * FROM {source_db}.{schema}.{table_name}",
                f"ON DUPLICATE KEY UPDATE updated_at=VALUES(updated_at);",
                "",
            ])
        return "\n".join(lines)

    @classmethod
    def generate_validation_script(cls, phase: int) -> str:
        phase_data = cls.MIGRATION_PHASES[phase - 1]
        lines = [
            f"-- Validation for Phase {phase}: {phase_data['name']}",
            f"-- {phase_data['validation']}",
            "",
        ]
        for table in phase_data["tables"]:
            lines.append(f"SELECT COUNT(*) AS cnt FROM {table};")
        return "\n".join(lines)
