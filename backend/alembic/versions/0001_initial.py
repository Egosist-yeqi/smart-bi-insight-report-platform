"""Create initial MySQL schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "0001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sales_order",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("external_order_id", sa.String(length=40), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("region", sa.String(length=20), nullable=False),
        sa.Column("province", sa.String(length=40), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("product_name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("customer_type", sa.String(length=40), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("profit", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_order_id", name="uq_sales_order_external_order_id"),
    )
    op.create_index("ix_sales_order_date_region", "sales_order", ["order_date", "region"])
    op.create_index(
        "ix_sales_order_category_customer",
        "sales_order",
        ["category", "customer_type"],
    )

    op.create_table(
        "metric_definition",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("metric_name", sa.String(length=80), nullable=False),
        sa.Column("metric_code", sa.String(length=60), nullable=False),
        sa.Column("formula", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("metric_code", name="uq_metric_definition_metric_code"),
    )

    op.create_table(
        "report_template",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("template_name", sa.String(length=120), nullable=False),
        sa.Column("report_type", sa.String(length=30), nullable=False),
        sa.Column("sections", mysql.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_name", name="uq_report_template_template_name"),
    )

    op.create_table(
        "ai_provider_config",
        sa.Column("id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("provider_name", sa.String(length=80), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=False),
        sa.Column("api_key_hint", sa.String(length=40), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "timeout_seconds", sa.Integer(), server_default=sa.text("30"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "query_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("engine", sa.String(length=20), nullable=False),
        sa.Column("intent_json", mysql.JSON(), nullable=True),
        sa.Column("generated_sql", sa.Text(), nullable=True),
        sa.Column("parameters_json", mysql.JSON(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_query_history_created_at", "query_history", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_query_history_created_at", table_name="query_history")
    op.drop_table("query_history")
    op.drop_table("ai_provider_config")
    op.drop_table("report_template")
    op.drop_table("metric_definition")
    op.drop_index("ix_sales_order_category_customer", table_name="sales_order")
    op.drop_index("ix_sales_order_date_region", table_name="sales_order")
    op.drop_table("sales_order")
