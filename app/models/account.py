from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    account_identifier: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    discovery_source: Mapped[str | None] = mapped_column(String(100), index=True)
    discovery_sender_email: Mapped[str | None] = mapped_column(String(255))
    discovery_subject: Mapped[str | None] = mapped_column(String(500))
    discovery_confidence_score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    company = relationship("Company", back_populates="accounts")
    gdpr_requests = relationship("GdprRequest", back_populates="account")
