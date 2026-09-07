"""add Gmail discovery classification metadata

Revision ID: 202609070005
Revises: 202608310004
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202609070005"
down_revision: str | None = "202608310004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("discovery_raw_domain", sa.String(length=255), nullable=True))
    op.add_column("companies", sa.Column("discovery_canonical_domain", sa.String(length=255), nullable=True))
    op.add_column("companies", sa.Column("discovery_classification", sa.String(length=32), nullable=True))
    op.add_column("companies", sa.Column("discovery_relationship", sa.String(length=100), nullable=True))
    op.add_column("companies", sa.Column("discovery_likely_controller", sa.String(length=500), nullable=True))
    op.add_column(
        "companies",
        sa.Column(
            "discovery_requires_controller_review",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "companies",
        sa.Column(
            "discovery_dsar_eligible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column("companies", sa.Column("discovery_classification_reason", sa.Text(), nullable=True))
    op.create_index(
        "ix_companies_discovery_canonical_domain",
        "companies",
        ["discovery_canonical_domain"],
        unique=False,
    )
    op.create_index(
        "ix_companies_discovery_classification",
        "companies",
        ["discovery_classification"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_companies_discovery_classification", table_name="companies")
    op.drop_index("ix_companies_discovery_canonical_domain", table_name="companies")
    op.drop_column("companies", "discovery_classification_reason")
    op.drop_column("companies", "discovery_dsar_eligible")
    op.drop_column("companies", "discovery_requires_controller_review")
    op.drop_column("companies", "discovery_likely_controller")
    op.drop_column("companies", "discovery_relationship")
    op.drop_column("companies", "discovery_classification")
    op.drop_column("companies", "discovery_canonical_domain")
    op.drop_column("companies", "discovery_raw_domain")
