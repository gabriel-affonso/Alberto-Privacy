"""add Alberto job retry tracking

Revision ID: 202609080005
Revises: 202608310004
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202609080005"
down_revision: str | None = "202608310004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("alberto_jobs", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("alberto_jobs", "attempts")
