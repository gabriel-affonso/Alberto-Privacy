from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class GdprRequest(Base):
    __tablename__ = "gdpr_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), index=True)
    controller_resolution_id: Mapped[int | None] = mapped_column(ForeignKey("controller_resolutions.id"), index=True)
    request_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(100), nullable=False, default="DRAFT")
    subject: Mapped[str | None] = mapped_column(String(500))
    body_text: Mapped[str | None] = mapped_column(Text)
    body_html: Mapped[str | None] = mapped_column(Text)
    legal_basis: Mapped[str | None] = mapped_column(String(255))
    identifiers_used: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False, default=list)
    template_version: Mapped[str | None] = mapped_column(String(100))
    ai_model: Mapped[str | None] = mapped_column(String(255))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    company = relationship("Company", back_populates="gdpr_requests")
    account = relationship("Account", back_populates="gdpr_requests")
    controller_resolution = relationship("ControllerResolution")
    communications = relationship("Communication", back_populates="gdpr_request")
    evidence_items = relationship("Evidence", back_populates="gdpr_request")
    privacy_case = relationship("PrivacyCase", back_populates="gdpr_request", uselist=False)
