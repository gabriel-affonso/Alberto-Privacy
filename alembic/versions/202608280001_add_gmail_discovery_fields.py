"""add gmail discovery fields

Revision ID: 202608280001
Revises: 202608270001
Create Date: 2026-08-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608280001"
down_revision: str | None = "202608270001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("domain", sa.String(length=255), nullable=True))
    op.add_column("companies", sa.Column("discovery_source", sa.String(length=100), nullable=True))
    op.add_column("companies", sa.Column("discovery_confidence_score", sa.Float(), nullable=True))
    op.add_column(
        "companies", sa.Column("discovery_first_seen_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "companies", sa.Column("discovery_last_seen_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "companies",
        sa.Column("discovery_message_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(op.f("ix_companies_domain"), "companies", ["domain"], unique=True)
    op.create_index(op.f("ix_companies_discovery_source"), "companies", ["discovery_source"], unique=False)

    op.add_column("accounts", sa.Column("discovery_source", sa.String(length=100), nullable=True))
    op.add_column("accounts", sa.Column("discovery_sender_email", sa.String(length=255), nullable=True))
    op.add_column("accounts", sa.Column("discovery_subject", sa.String(length=500), nullable=True))
    op.add_column("accounts", sa.Column("discovery_confidence_score", sa.Float(), nullable=True))
    op.create_index(op.f("ix_accounts_discovery_source"), "accounts", ["discovery_source"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_accounts_discovery_source"), table_name="accounts")
    op.drop_column("accounts", "discovery_confidence_score")
    op.drop_column("accounts", "discovery_subject")
    op.drop_column("accounts", "discovery_sender_email")
    op.drop_column("accounts", "discovery_source")

    op.drop_index(op.f("ix_companies_discovery_source"), table_name="companies")
    op.drop_index(op.f("ix_companies_domain"), table_name="companies")
    op.drop_column("companies", "discovery_message_count")
    op.drop_column("companies", "discovery_last_seen_at")
    op.drop_column("companies", "discovery_first_seen_at")
    op.drop_column("companies", "discovery_confidence_score")
    op.drop_column("companies", "discovery_source")
    op.drop_column("companies", "domain")
