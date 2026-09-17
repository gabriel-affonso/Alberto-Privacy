"""merge Alberto job retries, Telegram approvals, and Gmail discovery classification

Revision ID: 202609080007
Revises: 202609070005, 202609080006
Create Date: 2026-09-08
"""

from collections.abc import Sequence

revision: str = "202609080007"
down_revision: str | Sequence[str] | None = ("202609070005", "202609080006")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
