"""Add data import batch lineage."""

from alembic import op
import sqlalchemy as sa


revision = "0005_data_import_batches"
down_revision = "0004_decision_actions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_import_batch",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("scenario_id", sa.String(length=40), nullable=False),
        sa.Column("source_label", sa.String(length=160), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("data_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_import_batch_created_at", "data_import_batch", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_data_import_batch_created_at", table_name="data_import_batch")
    op.drop_table("data_import_batch")
