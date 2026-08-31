from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ControllerEvidence(Base):
    __tablename__ = "controller_evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    controller_resolution_id: Mapped[int] = mapped_column(ForeignKey("controller_resolutions.id"), index=True)
    field: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolution = relationship("ControllerResolution", back_populates="evidence_items")
