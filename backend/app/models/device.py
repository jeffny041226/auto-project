"""Device model."""
from datetime import datetime

from sqlalchemy import String, DateTime, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Device(Base):
    """Device database model."""

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    device_name: Mapped[str] = mapped_column(String(128), nullable=False)
    os_version: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="offline", index=True)
    current_task_id: Mapped[str] = mapped_column(String(64), nullable=True)
    last_heartbeat: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    tasks = relationship("Task", back_populates="device")

    def __repr__(self) -> str:
        return f"<Device(id={self.id}, device_id={self.device_id}, status={self.status})>"
