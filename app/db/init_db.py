from pathlib import Path

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
    Base.metadata.create_all(bind=get_engine())

