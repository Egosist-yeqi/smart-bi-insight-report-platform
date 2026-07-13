"""Add explicit private-network opt-in for AI providers."""

from alembic import op
import sqlalchemy as sa


revision = "0002_ai_network_policy"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_provider_config",
        sa.Column(
            "allow_private_network",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("ai_provider_config", "allow_private_network")
