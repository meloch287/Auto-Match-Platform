from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import BaseModel


class GlobalSettings(BaseModel):
    """Global platform settings stored in database."""

    __tablename__ = "global_settings"

    key: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )
    value: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    def __repr__(self) -> str:
        return f"<GlobalSettings(key={self.key}, value={self.value})>"
