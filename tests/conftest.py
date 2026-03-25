import pytest

from app.core.config import get_settings
from app.db.init_db import init_db
from app.db.models import SimpleTabulationCode
from app.db.session import get_engine, get_session_factory


def reset_settings_state() -> None:
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


@pytest.fixture
def db_session(monkeypatch, tmp_path):
    database_path = tmp_path / "test.db"
    monkeypatch.setenv("AUTH_TOKEN", "test-token")
    monkeypatch.setenv("SQLITE_PATH", str(database_path))
    monkeypatch.setenv("OPENROUTER_API_KEY", "")

    reset_settings_state()
    init_db()

    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
        reset_settings_state()


@pytest.fixture
def seeded_reference_data(db_session):
    rows = [
        SimpleTabulationCode(
            code="AB12",
            title="Alpha condition",
            parent_code=None,
            is_extension=False,
            sort_key=10,
            chapter_or_group="01",
            raw_row_json={"Code": "AB12"},
        ),
        SimpleTabulationCode(
            code="CD34",
            title="Delta qualifier",
            parent_code=None,
            is_extension=False,
            sort_key=20,
            chapter_or_group="01",
            raw_row_json={"Code": "CD34"},
        ),
        SimpleTabulationCode(
            code="XA123",
            title="Alpha extension",
            parent_code=None,
            is_extension=True,
            sort_key=100,
            chapter_or_group="X",
            raw_row_json={"Code": "XA123"},
        ),
        SimpleTabulationCode(
            code="XT9",
            title="Theta extension",
            parent_code=None,
            is_extension=True,
            sort_key=30,
            chapter_or_group="X",
            raw_row_json={"Code": "XT9"},
        ),
        SimpleTabulationCode(
            code="XY456",
            title="Psi extension",
            parent_code=None,
            is_extension=True,
            sort_key=40,
            chapter_or_group="X",
            raw_row_json={"Code": "XY456"},
        ),
    ]
    db_session.add_all(rows)
    db_session.commit()
    return rows

