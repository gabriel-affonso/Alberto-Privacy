"""add Telegram approval gate

Revision ID: 202609080006
Revises: 202609080005
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202609080006"
down_revision: str | None = "202609080005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("telegram_approvals", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("gdpr_request_id", sa.Integer(), sa.ForeignKey("gdpr_requests.id"), nullable=False), sa.Column("status", sa.String(length=30), nullable=False), sa.Column("token_hash", sa.String(length=64), nullable=False), sa.Column("telegram_message_id", sa.String(length=100)), sa.Column("approved_at", sa.DateTime(timezone=True)), sa.Column("rejected_at", sa.DateTime(timezone=True)), sa.Column("notified_at", sa.DateTime(timezone=True)), sa.Column("note", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("gdpr_request_id"))
    op.create_index("ix_telegram_approvals_gdpr_request_id", "telegram_approvals", ["gdpr_request_id"])
    op.create_index("ix_telegram_approvals_status", "telegram_approvals", ["status"])
    op.create_table("telegram_bot_state", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("update_offset", sa.Integer(), nullable=False))


def downgrade() -> None:
    op.drop_table("telegram_bot_state")
    op.drop_index("ix_telegram_approvals_status", table_name="telegram_approvals")
    op.drop_index("ix_telegram_approvals_gdpr_request_id", table_name="telegram_approvals")
    op.drop_table("telegram_approvals")
