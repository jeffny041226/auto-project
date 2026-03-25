"""Script model."""
from datetime import datetime

from sqlalchemy import String, DateTime, BigInteger, Integer, Text, LargeBinary, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Script(Base):
    """Script database model."""

    __tablename__ = "scripts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    script_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    intent: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    structured_instruction: Mapped[dict] = mapped_column(JSON, nullable=True)
    instruction_embedding: Mapped[bytes] = mapped_column(LargeBinary, nullable=True)
    pseudo_code: Mapped[str] = mapped_column(Text, nullable=True)
    maestro_yaml: Mapped[str] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user = relationship("User", back_populates="scripts")
    tasks = relationship("Task", back_populates="script")

    def __repr__(self) -> str:
        return f"<Script(id={self.id}, script_id={self.script_id}, intent={self.intent})>"
