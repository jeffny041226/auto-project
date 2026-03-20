"""TaskStep model."""
from datetime import datetime

from sqlalchemy import String, DateTime, BigInteger, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class TaskStep(Base):
    """TaskStep database model."""

    __tablename__ = "task_steps"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    step_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey("tasks.task_id"), nullable=False, index=True)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[str] = mapped_column(String(255), nullable=True)
    value: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    screenshot_before: Mapped[str] = mapped_column(String(512), nullable=True)
    screenshot_after: Mapped[str] = mapped_column(String(512), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fix_applied: Mapped[str] = mapped_column(String(255), nullable=True)
    error_detail: Mapped[str] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    task = relationship("Task", back_populates="steps")

    def __repr__(self) -> str:
        return f"<TaskStep(id={self.id}, step_id={self.step_id}, action={self.action})>"
