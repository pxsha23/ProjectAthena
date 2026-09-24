from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import get_settings
from app.core.db import Base, EmbeddingType, TZDateTime, utcnow
from app.models.user import new_id


class CodeChunk(Base):
    """A slice of a project file with its embedding, used for semantic code search."""

    __tablename__ = "code_chunks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    file_path: Mapped[str] = mapped_column(String(500))
    start_line: Mapped[int] = mapped_column(Integer)
    end_line: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(EmbeddingType(get_settings().embedding_dim))
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), default=utcnow)
