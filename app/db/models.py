from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    return datetime.now(UTC)


class SimpleTabulationCode(Base):
    __tablename__ = "simple_tabulation_codes"
    __table_args__ = (
        Index("ix_simple_tabulation_codes_code", "code"),
        Index("ix_simple_tabulation_codes_sort_key", "sort_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    parent_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_extension: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_key: Mapped[int] = mapped_column(Integer, nullable=False)
    chapter_or_group: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_row_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class GeneratedCache(Base):
    __tablename__ = "generated_cache"
    __table_args__ = (
        Index("ix_generated_cache_normalized_code", "normalized_code"),
        Index("ix_generated_cache_response_hash", "response_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    input_code: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_code: Mapped[str] = mapped_column(String(255), nullable=False)
    include_ai_phrase: Mapped[bool] = mapped_column(Boolean, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    ai_phrase: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    response_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class NormalizedResult(Base):
    __tablename__ = "normalized_results"
    __table_args__ = (
        Index("ix_normalized_results_normalized_code", "normalized_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    normalized_code: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    ai_phrase: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
