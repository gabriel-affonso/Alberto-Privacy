"""add controller resolutions

Revision ID: 202608280002
Revises: 202608280001
Create Date: 2026-08-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608280002"
down_revision: str | None = "202608280001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "controller_resolutions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("brand", sa.String(length=255), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("controller_name", sa.String(length=500), nullable=False),
        sa.Column("controller_country", sa.String(length=255), nullable=False),
        sa.Column("privacy_policy_url", sa.String(length=1000), nullable=False),
        sa.Column("privacy_request_url", sa.String(length=1000), nullable=False),
        sa.Column("dpo_contact", sa.String(length=500), nullable=False),
        sa.Column("request_method", sa.String(length=50), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("queried_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"], name=op.f("fk_controller_resolutions_company_id_companies")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_controller_resolutions")),
    )
    op.create_index(
        op.f("ix_controller_resolutions_company_id"),
        "controller_resolutions",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_controller_resolutions_domain"),
        "controller_resolutions",
        ["domain"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_controller_resolutions_domain"), table_name="controller_resolutions")
    op.drop_index(op.f("ix_controller_resolutions_company_id"), table_name="controller_resolutions")
    op.drop_table("controller_resolutions")
