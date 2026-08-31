from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ControllerResolution(Base):
    __tablename__ = "controller_resolutions"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    brand: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    controller_name: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    controller_country: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    controller_address: Mapped[str] = mapped_column(Text, nullable=False, default="")
    privacy_policy_url: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    privacy_request_url: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    dpo_contact: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    request_method: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    conflicts: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    queried_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    company = relationship("Company", back_populates="controller_resolutions")
    evidence_items = relationship("ControllerEvidence", back_populates="resolution", cascade="all, delete-orphan")
