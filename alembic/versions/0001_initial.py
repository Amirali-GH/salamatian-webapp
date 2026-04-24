"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("admin", "operator", "viewer", name="user_role"),
            nullable=False,
            server_default="viewer",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "cars",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("brand", sa.String(100), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(18, 2), nullable=False),
        sa.Column("mileage", sa.Integer(), nullable=True),
        sa.Column(
            "gearbox",
            sa.Enum("manual", "automatic", "cvt", "dct", name="gearbox"),
            nullable=True,
        ),
        sa.Column(
            "fuel_type",
            sa.Enum("gasoline", "diesel", "hybrid", "electric", "lpg", "cng", name="fuel_type"),
            nullable=True,
        ),
        sa.Column("color", sa.String(50), nullable=True),
        sa.Column("body_status", sa.String(100), nullable=True),
        sa.Column("location", sa.String(100), nullable=True),
        sa.Column("engine_volume", sa.String(50), nullable=True),
        sa.Column("engine_power", sa.String(50), nullable=True),
        sa.Column("acceleration", sa.String(50), nullable=True),
        sa.Column("fuel_consumption", sa.String(50), nullable=True),
        sa.Column("brake_system", sa.String(100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("features_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("images_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "status",
            sa.Enum("draft", "pending", "published", "archived", name="car_status"),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "source",
            sa.Enum("manual", "excel", "user_submission", name="car_source"),
            nullable=False,
            server_default="manual",
        ),
        sa.Column("excel_row_id", sa.String(100), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("excel_row_id", name="uq_cars_excel_row_id"),
    )
    op.create_index("ix_cars_brand", "cars", ["brand"])
    op.create_index("ix_cars_model", "cars", ["model"])
    op.create_index("ix_cars_year", "cars", ["year"])
    op.create_index("ix_cars_location", "cars", ["location"])
    op.create_index("ix_cars_status", "cars", ["status"])
    op.create_index("ix_cars_source", "cars", ["source"])
    op.create_index("ix_cars_excel_row_id", "cars", ["excel_row_id"])
    op.create_index("ix_cars_brand_model_year", "cars", ["brand", "model", "year"])
    op.create_index("ix_cars_status_source", "cars", ["status", "source"])
    op.create_index("ix_cars_created_at", "cars", ["created_at"])

    op.create_table(
        "car_images",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("car_id", sa.BigInteger(), sa.ForeignKey("cars.id", ondelete="CASCADE"), nullable=False),
        sa.Column("image_path", sa.String(512), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_car_images_car_id", "car_images", ["car_id"])

    op.create_table(
        "car_seo",
        sa.Column("car_id", sa.BigInteger(), sa.ForeignKey("cars.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("meta_title", sa.String(255), nullable=True),
        sa.Column("meta_description", sa.String(500), nullable=True),
        sa.Column("slug", sa.String(255), unique=True, nullable=True),
        sa.Column("schema_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_car_seo_slug", "car_seo", ["slug"])

    op.create_table(
        "leads",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "type",
            sa.Enum("consultation", "sell_request", name="lead_type"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("phone", sa.String(32), nullable=False),
        sa.Column("car_brand", sa.String(100), nullable=True),
        sa.Column("car_model", sa.String(100), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("mileage", sa.Integer(), nullable=True),
        sa.Column("color", sa.String(50), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("images_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "status",
            sa.Enum("new", "contacted", "converted", "closed", name="lead_status"),
            nullable=False,
            server_default="new",
        ),
        sa.Column("operator_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_leads_type", "leads", ["type"])
    op.create_index("ix_leads_phone", "leads", ["phone"])
    op.create_index("ix_leads_status", "leads", ["status"])

    op.create_table(
        "excel_import_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("file_path", sa.String(512), nullable=False),
        sa.Column("imported_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("added_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("removed_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "applied_by_user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_excel_import_logs_applied_by_user_id", "excel_import_logs", ["applied_by_user_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "action",
            sa.Enum(
                "create",
                "update",
                "delete",
                "archive",
                "publish",
                "price_change",
                "login",
                "logout",
                name="audit_action",
            ),
            nullable=False,
        ),
        sa.Column("old_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column(
            "channel",
            sa.Enum("admin_panel", "telegram", "email", name="notification_channel"),
            nullable=False,
            server_default="admin_panel",
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_channel", "notifications", ["channel"])
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("audit_logs")
    op.drop_table("excel_import_logs")
    op.drop_table("leads")
    op.drop_table("car_seo")
    op.drop_table("car_images")
    op.drop_table("cars")
    op.drop_table("users")
    sa.Enum(name="notification_channel").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="audit_action").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="lead_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="lead_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="car_source").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="car_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="fuel_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="gearbox").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="user_role").drop(op.get_bind(), checkfirst=True)
