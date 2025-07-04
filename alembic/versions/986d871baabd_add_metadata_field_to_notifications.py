"""add metadata field to notifications

Revision ID: 986d871baabd
Revises: afca1e3d4768
Create Date: 2025-05-28 04:30:35.583977

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "986d871baabd"
down_revision: Union[str, None] = "afca1e3d4768"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("notifications", sa.Column("extra_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("notifications", "extra_data")
    # ### end Alembic commands ###
