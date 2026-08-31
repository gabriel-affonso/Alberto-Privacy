from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PrivacyCase(Base):
    __tablename__ = "privacy_cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    gdpr_request_id: Mapped[int] = mapped_column(ForeignKey("gdpr_requests.id"), unique=True, index=True)
    request_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(100), nullable=False, default="DRAFT", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deadline: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    extension_deadline: Mapped[date | None] = mapped_column(Date)
    extension_note: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    company = relationship("Company", back_populates="cases")
    gdpr_request = relationship("GdprRequest", back_populates="privacy_case")
    events = relationship("CaseEvent", back_populates="privacy_case", cascade="all, delete-orphan", order_by="CaseEvent.created_at")
    response_files = relationship("ResponseFile", back_populates="privacy_case", cascade="all, delete-orphan")


class CaseEvent(Base):
    __tablename__ = "case_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("privacy_cases.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(100))
    to_status: Mapped[str | None] = mapped_column(String(100))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    privacy_case = relationship("PrivacyCase", back_populates="events")
