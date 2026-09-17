from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    domain: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    website: Mapped[str | None] = mapped_column(String(500))
    privacy_email: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    discovery_source: Mapped[str | None] = mapped_column(String(100), index=True)
    discovery_confidence_score: Mapped[float | None] = mapped_column(Float)
    discovery_first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discovery_last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discovery_message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    discovery_raw_domain: Mapped[str | None] = mapped_column(String(255))
    discovery_canonical_domain: Mapped[str | None] = mapped_column(String(255), index=True)
    discovery_classification: Mapped[str | None] = mapped_column(String(32), index=True)
    discovery_relationship: Mapped[str | None] = mapped_column(String(100))
    discovery_likely_controller: Mapped[str | None] = mapped_column(String(500))
    discovery_requires_controller_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    discovery_dsar_eligible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    discovery_classification_reason: Mapped[str | None] = mapped_column(Text)
    controller_name: Mapped[str | None] = mapped_column(String(500))
    controller_country: Mapped[str | None] = mapped_column(String(255))
    controller_address: Mapped[str | None] = mapped_column(Text)
    privacy_policy_url: Mapped[str | None] = mapped_column(String(1000))
    privacy_request_url: Mapped[str | None] = mapped_column(String(1000))
    dpo_contact: Mapped[str | None] = mapped_column(String(500))
    request_method: Mapped[str | None] = mapped_column(String(50))
    resolver_confidence: Mapped[float | None] = mapped_column(Float)
    last_resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    accounts = relationship("Account", back_populates="company", cascade="all, delete-orphan")
    gdpr_requests = relationship("GdprRequest", back_populates="company")
    controller_resolutions = relationship("ControllerResolution", back_populates="company")
    cases = relationship("PrivacyCase", back_populates="company")
