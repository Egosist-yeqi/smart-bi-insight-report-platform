"""Add active industry-scenario state."""

from alembic import op
import sqlalchemy as sa


revision = "0003_scenario_state"
down_revision = "0002_ai_network_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scenario_state",
        sa.Column("id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("scenario_id", sa.String(length=40), nullable=False),
        sa.Column("data_source", sa.String(length=20), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("scenario_state")
