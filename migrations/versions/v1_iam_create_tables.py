"""create iam domain tables

Revision ID: v1_iam
Revises:
Create Date: 2026-04-27
"""
from alembic import op
import sqlalchemy as sa

revision = "v1_iam"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS iam")

    op.create_table(
        "tenant",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, comment="Tenant name"),
        sa.Column("code", sa.String(50), nullable=False, unique=True, comment="Tenant code"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("plan", sa.String(30), nullable=False, server_default="free"),
        sa.Column("max_users", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("max_stores", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contact_name", sa.String(100), nullable=False, server_default=""),
        sa.Column("contact_email", sa.String(200), nullable=False, server_default=""),
        sa.Column("contact_phone", sa.String(30), nullable=False, server_default=""),
        sa.Column("logo_url", sa.String(500), nullable=False, server_default=""),
        sa.Column("config_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="iam",
    )

    op.create_table(
        "organization",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("parent_id", sa.String(36), nullable=True, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("org_type", sa.String(30), nullable=False, server_default="company"),
        sa.Column("path", sa.String(500), nullable=False, server_default=""),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("leader_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="iam",
    )

    op.create_table(
        "user",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("org_id", sa.String(36), nullable=True, index=True),
        sa.Column("username", sa.String(80), nullable=False),
        sa.Column("email", sa.String(200), nullable=False, server_default=""),
        sa.Column("phone", sa.String(30), nullable=False, server_default=""),
        sa.Column("password_hash", sa.String(200), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False, server_default=""),
        sa.Column("avatar_url", sa.String(500), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("user_type", sa.String(20), nullable=False, server_default="internal"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_ip", sa.String(50), nullable=False, server_default=""),
        sa.Column("login_fail_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("must_change_pwd", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="iam",
    )

    op.create_table(
        "role",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
        sa.Column("role_type", sa.String(20), nullable=False, server_default="custom"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="iam",
    )

    op.create_table(
        "permission",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("parent_id", sa.String(36), nullable=True, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("code", sa.String(100), nullable=False, unique=True),
        sa.Column("perm_type", sa.String(20), nullable=False),
        sa.Column("resource", sa.String(200), nullable=False, server_default=""),
        sa.Column("action", sa.String(50), nullable=False, server_default=""),
        sa.Column("path", sa.String(500), nullable=False, server_default=""),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("icon", sa.String(100), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="iam",
    )

    op.create_table(
        "user_role",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("role_id", sa.String(36), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="iam",
    )

    op.create_table(
        "role_permission",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("role_id", sa.String(36), nullable=False, index=True),
        sa.Column("permission_id", sa.String(36), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="iam",
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("user_name", sa.String(100), nullable=False, server_default=""),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("module", sa.String(50), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False, server_default=""),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("ip", sa.String(50), nullable=False, server_default=""),
        sa.Column("trace_id", sa.String(36), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="iam",
    )

    op.create_index("ix_iam_user_tenant_username", "user", ["tenant_id", "username"], schema="iam", unique=True)
    op.create_index("ix_iam_role_tenant_code", "role", ["tenant_id", "code"], schema="iam", unique=True)
    op.create_index("ix_iam_org_tenant_code", "organization", ["tenant_id", "code"], schema="iam", unique=True)
    op.create_index("ix_iam_user_role_unique", "user_role", ["user_id", "role_id", "tenant_id"], schema="iam", unique=True)
    op.create_index("ix_iam_role_perm_unique", "role_permission", ["role_id", "permission_id"], schema="iam", unique=True)


def downgrade() -> None:
    op.drop_table("audit_log", schema="iam")
    op.drop_table("role_permission", schema="iam")
    op.drop_table("user_role", schema="iam")
    op.drop_table("permission", schema="iam")
    op.drop_table("role", schema="iam")
    op.drop_table("user", schema="iam")
    op.drop_table("organization", schema="iam")
    op.drop_table("tenant", schema="iam")
    op.execute("DROP SCHEMA IF EXISTS iam CASCADE")
