"""add restricted Alberto job bridge

Revision ID: 202608310004
Revises: 202608300003
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608310004"
down_revision: str | None = "202608300003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alberto_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("controller_resolution_id", sa.Integer(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("claimed_by", sa.String(length=255), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["controller_resolution_id"], ["controller_resolutions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alberto_jobs_job_type", "alberto_jobs", ["job_type"], unique=False)
    op.create_index("ix_alberto_jobs_status", "alberto_jobs", ["status"], unique=False)
    op.create_index("ix_alberto_jobs_controller_resolution_id", "alberto_jobs", ["controller_resolution_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_alberto_jobs_controller_resolution_id", table_name="alberto_jobs")
    op.drop_index("ix_alberto_jobs_status", table_name="alberto_jobs")
    op.drop_index("ix_alberto_jobs_job_type", table_name="alberto_jobs")
    op.drop_table("alberto_jobs")
