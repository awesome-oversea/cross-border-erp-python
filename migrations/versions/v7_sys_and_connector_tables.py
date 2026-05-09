from alembic import op
import sqlalchemy as sa

revision = "v7_sys_and_connector_tables"
down_revision = "v6_middleware_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS sys")

    op.create_table("dict_type",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("code", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="sys",
    )

    op.create_table("dict_item",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("type_code", sa.String(100), nullable=False, index=True),
        sa.Column("item_code", sa.String(100), nullable=False),
        sa.Column("item_value", sa.String(500), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="sys",
    )

    op.create_table("sys_param",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("param_key", sa.String(200), nullable=False, unique=True),
        sa.Column("param_value", sa.Text, nullable=False, server_default=""),
        sa.Column("param_type", sa.String(30), nullable=False, server_default="string"),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="sys",
    )

    op.create_table("biz_rule",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("domain", sa.String(50), nullable=False, index=True),
        sa.Column("rule_code", sa.String(100), nullable=False),
        sa.Column("rule_name", sa.String(200), nullable=False),
        sa.Column("rule_type", sa.String(50), nullable=False, server_default="validation"),
        sa.Column("condition_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("action_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="sys",
    )

    op.create_table("ai_switch",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("domain", sa.String(50), nullable=False, index=True),
        sa.Column("feature_key", sa.String(100), nullable=False),
        sa.Column("feature_name", sa.String(200), nullable=False),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("config_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="sys",
    )

    op.create_table("connector_config",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("connector_id", sa.String(100), nullable=False, unique=True),
        sa.Column("connector_name", sa.String(200), nullable=False),
        sa.Column("connector_type", sa.String(30), nullable=False, index=True),
        sa.Column("base_url", sa.String(500), nullable=False, server_default=""),
        sa.Column("api_key_encrypted", sa.Text, nullable=False, server_default=""),
        sa.Column("api_secret_encrypted", sa.Text, nullable=False, server_default=""),
        sa.Column("extra_config_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("rate_limit_per_min", sa.Integer, nullable=False, server_default="60"),
        sa.Column("timeout_seconds", sa.Integer, nullable=False, server_default="30"),
        sa.Column("store_id", sa.String(36), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="sys",
    )

    op.create_table("store_auth",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("store_id", sa.String(36), nullable=False, index=True),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("auth_token_encrypted", sa.Text, nullable=False, server_default=""),
        sa.Column("refresh_token_encrypted", sa.Text, nullable=False, server_default=""),
        sa.Column("auth_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auth_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="sys",
    )

    op.create_table("webhook_config",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("webhook_url", sa.String(500), nullable=False),
        sa.Column("event_types_json", sa.Text, nullable=False, server_default="[]"),
        sa.Column("secret_key_encrypted", sa.Text, nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="3"),
        sa.Column("timeout_seconds", sa.Integer, nullable=False, server_default="30"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="sys",
    )

    op.create_table("secret_store",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("secret_key", sa.String(200), nullable=False, unique=True),
        sa.Column("secret_value_encrypted", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="sys",
    )

    op.create_table("event_catalog",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_type", sa.String(200), nullable=False, unique=True),
        sa.Column("domain", sa.String(50), nullable=False, index=True),
        sa.Column("aggregate_type", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("payload_schema_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("version", sa.String(10), nullable=False, server_default="v1"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="sys",
    )

    op.create_table("import_task",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("task_type", sa.String(50), nullable=False),
        sa.Column("file_key", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending", index=True),
        sa.Column("total_rows", sa.Integer, nullable=False, server_default="0"),
        sa.Column("success_rows", sa.Integer, nullable=False, server_default="0"),
        sa.Column("fail_rows", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_detail_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("created_by", sa.String(36), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="sys",
    )

    op.create_table("doc_number_rule",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("domain", sa.String(50), nullable=False, index=True),
        sa.Column("doc_type", sa.String(50), nullable=False),
        sa.Column("prefix", sa.String(20), nullable=False, server_default=""),
        sa.Column("date_format", sa.String(20), nullable=False, server_default="%Y%m%d"),
        sa.Column("seq_length", sa.Integer, nullable=False, server_default="4"),
        sa.Column("current_seq", sa.Integer, nullable=False, server_default="0"),
        sa.Column("reset_rule", sa.String(20), nullable=False, server_default="daily"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="sys",
    )

    op.create_table("risk_alert",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("recommendation_id", sa.String(36), nullable=False, server_default="", index=True),
        sa.Column("domain", sa.String(50), nullable=False, index=True),
        sa.Column("risk_type", sa.String(50), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("evidence_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open", index=True),
        sa.Column("assigned_to", sa.String(36), nullable=False, server_default=""),
        sa.Column("resolution", sa.Text, nullable=False, server_default=""),
        sa.Column("idempotency_key", sa.String(200), nullable=False, server_default="", index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="sys",
    )

    op.create_table("insight_card",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("recommendation_id", sa.String(36), nullable=False, server_default="", index=True),
        sa.Column("domain", sa.String(50), nullable=False, index=True),
        sa.Column("card_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("metrics_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active", index=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(200), nullable=False, server_default="", index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="sys",
    )

    op.create_table("connector_health_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("connector_id", sa.String(100), nullable=False, index=True),
        sa.Column("connector_type", sa.String(30), nullable=False),
        sa.Column("health_status", sa.String(20), nullable=False),
        sa.Column("response_time_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text, nullable=False, server_default=""),
        sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="sys",
    )


def downgrade() -> None:
    tables = [
        "connector_health_log", "insight_card", "risk_alert", "doc_number_rule",
        "import_task", "event_catalog", "secret_store", "webhook_config",
        "store_auth", "connector_config", "ai_switch", "biz_rule",
        "sys_param", "dict_item", "dict_type",
    ]
    for table in tables:
        op.drop_table(table, schema="sys")
