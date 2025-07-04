"""add RateLimitLog in models.py

Revision ID: efff0e0dc480
Revises: 986d871baabd
Create Date: 2025-05-29 08:02:22.869375

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "efff0e0dc480"
down_revision: Union[str, None] = "986d871baabd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "rate_limit_logs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("endpoint", sa.String(), nullable=False),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_rate_limit_logs_created_at"), "rate_limit_logs", ["created_at"], unique=False)
    op.create_index(op.f("ix_rate_limit_logs_email"), "rate_limit_logs", ["email"], unique=False)
    op.create_index(op.f("ix_rate_limit_logs_id"), "rate_limit_logs", ["id"], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_rate_limit_logs_id"), table_name="rate_limit_logs")
    op.drop_index(op.f("ix_rate_limit_logs_email"), table_name="rate_limit_logs")
    op.drop_index(op.f("ix_rate_limit_logs_created_at"), table_name="rate_limit_logs")
    op.drop_table("rate_limit_logs")
    # ### end Alembic commands ###
