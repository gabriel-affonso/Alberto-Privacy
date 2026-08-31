"""initial schema

Revision ID: 202608270001
Revises:
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608270001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("website", sa.String(length=500), nullable=True),
        sa.Column("privacy_email", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_companies")),
    )
    op.create_index(op.f("ix_companies_name"), "companies", ["name"], unique=False)

    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("account_identifier", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name=op.f("fk_accounts_company_id_companies")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_accounts")),
    )
    op.create_index(op.f("ix_accounts_company_id"), "accounts", ["company_id"], unique=False)

    op.create_table(
        "gdpr_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("request_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=100), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name=op.f("fk_gdpr_requests_account_id_accounts")),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name=op.f("fk_gdpr_requests_company_id_companies")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gdpr_requests")),
    )
    op.create_index(op.f("ix_gdpr_requests_account_id"), "gdpr_requests", ["account_id"], unique=False)
    op.create_index(op.f("ix_gdpr_requests_company_id"), "gdpr_requests", ["company_id"], unique=False)

    op.create_table(
        "communications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("gdpr_request_id", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(length=50), nullable=False),
        sa.Column("channel", sa.String(length=50), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["gdpr_request_id"],
            ["gdpr_requests.id"],
            name=op.f("fk_communications_gdpr_request_id_gdpr_requests"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_communications")),
    )
    op.create_index(
        op.f("ix_communications_gdpr_request_id"), "communications", ["gdpr_request_id"], unique=False
    )

    op.create_table(
        "evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("gdpr_request_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("evidence_type", sa.String(length=100), nullable=False),
        sa.Column("storage_path", sa.String(length=1000), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["gdpr_request_id"],
            ["gdpr_requests.id"],
            name=op.f("fk_evidence_gdpr_request_id_gdpr_requests"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evidence")),
    )
    op.create_index(op.f("ix_evidence_gdpr_request_id"), "evidence", ["gdpr_request_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_evidence_gdpr_request_id"), table_name="evidence")
    op.drop_table("evidence")
    op.drop_index(op.f("ix_communications_gdpr_request_id"), table_name="communications")
    op.drop_table("communications")
    op.drop_index(op.f("ix_gdpr_requests_company_id"), table_name="gdpr_requests")
    op.drop_index(op.f("ix_gdpr_requests_account_id"), table_name="gdpr_requests")
    op.drop_table("gdpr_requests")
    op.drop_index(op.f("ix_accounts_company_id"), table_name="accounts")
    op.drop_table("accounts")
    op.drop_index(op.f("ix_companies_name"), table_name="companies")
    op.drop_table("companies")

