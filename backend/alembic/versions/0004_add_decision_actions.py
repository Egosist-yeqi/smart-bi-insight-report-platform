"""Add decision action tracking."""

from alembic import op
import sqlalchemy as sa


revision = "0004_decision_actions"
down_revision = "0003_scenario_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "decision_action",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("owner", sa.String(length=80), nullable=True),
        sa.Column("priority", sa.String(length=12), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("target_metric", sa.String(length=80), nullable=True),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
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
    op.create_index(
        "ix_decision_action_status_due_date",
        "decision_action",
        ["status", "due_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_decision_action_status_due_date", table_name="decision_action")
    op.drop_table("decision_action")
