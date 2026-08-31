"""add request lifecycle, controller evidence, and response provenance

Revision ID: 202608300003
Revises: 202608280002
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608300003"
down_revision: str | None = "202608280002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _finding_table(name: str, extra: list[sa.Column] | None = None) -> None:
    op.create_table(
        name,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("response_file_id", sa.Integer(), nullable=False),
        sa.Column("value_redacted", sa.Text(), nullable=True),
        sa.Column("value_hash", sa.String(length=64), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("position", sa.String(length=500), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("extraction_method", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        *(extra or []),
        sa.ForeignKeyConstraint(["response_file_id"], ["response_files.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(f"ix_{name}_response_file_id", name, ["response_file_id"], unique=False)
    op.create_index(f"ix_{name}_value_hash", name, ["value_hash"], unique=False)


def upgrade() -> None:
    for column in (
        sa.Column("controller_name", sa.String(length=500)), sa.Column("controller_country", sa.String(length=255)),
        sa.Column("controller_address", sa.Text()), sa.Column("privacy_policy_url", sa.String(length=1000)),
        sa.Column("privacy_request_url", sa.String(length=1000)), sa.Column("dpo_contact", sa.String(length=500)),
        sa.Column("request_method", sa.String(length=50)), sa.Column("resolver_confidence", sa.Float()),
        sa.Column("last_resolved_at", sa.DateTime(timezone=True)),
    ):
        op.add_column("companies", column)
    op.add_column("controller_resolutions", sa.Column("controller_address", sa.Text(), nullable=False, server_default=""))
    op.add_column("controller_resolutions", sa.Column("conflicts", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.create_table(
        "controller_evidence", sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("controller_resolution_id", sa.Integer(), nullable=False), sa.Column("field", sa.String(length=100), nullable=False),
        sa.Column("value", sa.String(length=1000), nullable=False), sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False), sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["controller_resolution_id"], ["controller_resolutions.id"]), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_controller_evidence_controller_resolution_id", "controller_evidence", ["controller_resolution_id"], unique=False)

    for column in (
        sa.Column("controller_resolution_id", sa.Integer()), sa.Column("subject", sa.String(length=500)), sa.Column("body_text", sa.Text()),
        sa.Column("body_html", sa.Text()), sa.Column("legal_basis", sa.String(length=255)), sa.Column("identifiers_used", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("template_version", sa.String(length=100)), sa.Column("ai_model", sa.String(length=255)), sa.Column("content_hash", sa.String(length=64)),
        sa.Column("generated_at", sa.DateTime(timezone=True)), sa.Column("approved_at", sa.DateTime(timezone=True)),
    ):
        op.add_column("gdpr_requests", column)
    with op.batch_alter_table("gdpr_requests") as batch:
        batch.create_foreign_key("fk_gdpr_requests_controller_resolution_id", "controller_resolutions", ["controller_resolution_id"], ["id"])
        batch.create_index("ix_gdpr_requests_controller_resolution_id", ["controller_resolution_id"], unique=False)
    op.create_table(
        "privacy_cases", sa.Column("id", sa.Integer(), nullable=False), sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("gdpr_request_id", sa.Integer(), nullable=False), sa.Column("request_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=100), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True)), sa.Column("sent_at", sa.DateTime(timezone=True)), sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("deadline", sa.Date()), sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("extension_deadline", sa.Date()),
        sa.Column("extension_note", sa.Text()), sa.Column("notes", sa.Text()),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]), sa.ForeignKeyConstraint(["gdpr_request_id"], ["gdpr_requests.id"]), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gdpr_request_id"),
    )
    op.create_index("ix_privacy_cases_company_id", "privacy_cases", ["company_id"], unique=False)
    op.create_index("ix_privacy_cases_gdpr_request_id", "privacy_cases", ["gdpr_request_id"], unique=True)
    op.create_index("ix_privacy_cases_status", "privacy_cases", ["status"], unique=False)
    op.create_table(
        "case_events", sa.Column("id", sa.Integer(), nullable=False), sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False), sa.Column("from_status", sa.String(length=100)), sa.Column("to_status", sa.String(length=100)),
        sa.Column("note", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["privacy_cases.id"]), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_case_events_case_id", "case_events", ["case_id"], unique=False)
    for column in (
        sa.Column("gmail_message_id", sa.String(length=255)), sa.Column("gmail_thread_id", sa.String(length=255)),
        sa.Column("rfc822_path", sa.String(length=1000)), sa.Column("content_hash", sa.String(length=64)), sa.Column("sender", sa.String(length=500)),
    ):
        op.add_column("communications", column)
    op.create_index("ix_communications_gmail_message_id", "communications", ["gmail_message_id"], unique=False)
    op.create_index("ix_communications_gmail_thread_id", "communications", ["gmail_thread_id"], unique=False)

    op.create_table(
        "response_files", sa.Column("id", sa.Integer(), nullable=False), sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("original_name", sa.String(length=500), nullable=False), sa.Column("media_type", sa.String(length=255)),
        sa.Column("storage_path", sa.String(length=1000), nullable=False), sa.Column("sha256", sa.String(length=64), nullable=False), sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["privacy_cases.id"]), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_response_files_case_id", "response_files", ["case_id"], unique=False)
    op.create_index("ix_response_files_sha256", "response_files", ["sha256"], unique=False)
    _finding_table("personal_data_items", [sa.Column("category", sa.String(length=100), nullable=False)])
    op.create_index("ix_personal_data_items_category", "personal_data_items", ["category"], unique=False)
    for name in ("data_sources", "data_recipients", "profiling_items", "advertising_data", "devices", "locations", "data_transfers", "retention_information", "automated_decision_information"):
        _finding_table(name)
    _finding_table("identifiers", [sa.Column("identifier_type", sa.String(length=100), nullable=False)])
    op.create_index("ix_identifiers_identifier_type", "identifiers", ["identifier_type"], unique=False)
    op.create_table(
        "provenance_entities", sa.Column("id", sa.Integer(), nullable=False), sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=500)), sa.Column("value_hash", sa.String(length=64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_provenance_entities_entity_type", "provenance_entities", ["entity_type"], unique=False)
    op.create_index("ix_provenance_entities_value_hash", "provenance_entities", ["value_hash"], unique=False)
    op.create_table(
        "provenance_relations", sa.Column("id", sa.Integer(), nullable=False), sa.Column("from_entity_id", sa.Integer(), nullable=False),
        sa.Column("to_entity_id", sa.Integer(), nullable=False), sa.Column("relation_type", sa.String(length=100), nullable=False),
        sa.Column("response_file_id", sa.Integer(), nullable=False), sa.Column("evidence_excerpt", sa.Text(), nullable=False), sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["from_entity_id"], ["provenance_entities.id"]), sa.ForeignKeyConstraint(["to_entity_id"], ["provenance_entities.id"]),
        sa.ForeignKeyConstraint(["response_file_id"], ["response_files.id"]), sa.PrimaryKeyConstraint("id"),
    )
    for column in ("from_entity_id", "to_entity_id", "relation_type", "response_file_id"):
        op.create_index(f"ix_provenance_relations_{column}", "provenance_relations", [column], unique=False)


def downgrade() -> None:
    # The migration is intentionally additive. Downgrading data-bearing privacy tables is unsupported.
    raise RuntimeError("Downgrade is not supported for privacy data migrations")
