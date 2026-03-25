from pathlib import Path

from sqlalchemy import inspect, text

from app.core.config import get_settings
from app.db.models import Base
from app.db.session import get_engine


def _ensure_sqlite_parent_dir() -> None:
    settings = get_settings()
    sqlite_path = settings.sqlite_path
    if sqlite_path.startswith("sqlite") or sqlite_path == ":memory:":
        return
    Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)


def init_db() -> None:
    _ensure_sqlite_parent_dir()
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    _ensure_runtime_columns(engine)


def _ensure_runtime_columns(engine) -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    if "generated_cache" in table_names:
        columns = {column["name"] for column in inspector.get_columns("generated_cache")}
        if "resolved_model_name" not in columns:
            with engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE generated_cache ADD COLUMN resolved_model_name VARCHAR(255)")
                )
