"""add supplier to cars and make year nullable

Revision ID: 0002_add_supplier_year_nullable
Revises: 0001_initial
Create Date: 2026-05-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_add_supplier_year_nullable"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("cars", sa.Column("supplier", sa.String(150), nullable=True))
    op.alter_column("cars", "year", nullable=True)


def downgrade() -> None:
    op.drop_column("cars", "supplier")
    op.alter_column("cars", "year", nullable=False)
