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
    monkeypatch.setenv("OCL_TOKEN", "")
    monkeypatch.setenv("OCL_LOOKUP_SOURCE", "/orgs/OpenMRS-OCL-Squad/sources/ICD-11-WHO-Mapper/")

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
            parent_code="BLOCK-1",
            is_extension=False,
            sort_key=10,
            chapter_or_group="01",
            raw_row_json={
                "Code": "AB12",
                "ChapterNo": "01",
                "BlockId": "BLOCK-1",
                "ClassKind": "category",
            },
        ),
        SimpleTabulationCode(
            code="CD34",
            title="Delta qualifier",
            parent_code=None,
            is_extension=True,
            sort_key=20,
            chapter_or_group="01",
            raw_row_json={
                "Code": "CD34",
                "ChapterNo": "01",
                "ClassKind": "extension",
            },
        ),
        SimpleTabulationCode(
            code="EF56",
            title="Echo disorder",
            parent_code="BLOCK-1",
            is_extension=False,
            sort_key=5,
            chapter_or_group="01",
            raw_row_json={
                "Code": "EF56",
                "ChapterNo": "01",
                "BlockId": "BLOCK-1",
                "ClassKind": "category",
            },
        ),
        SimpleTabulationCode(
            code="BLOCK-1",
            title="Block One",
            parent_code="CH1",
            is_extension=False,
            sort_key=5,
            chapter_or_group="01",
            raw_row_json={
                "Code": "BLOCK-1",
                "ChapterNo": "01",
                "ClassKind": "block",
            },
        ),
        SimpleTabulationCode(
            code="CH1",
            title="Chapter One",
            parent_code=None,
            is_extension=False,
            sort_key=1,
            chapter_or_group="01",
            raw_row_json={
                "Code": "CH1",
                "ChapterNo": "01",
                "ClassKind": "chapter",
            },
        ),
        SimpleTabulationCode(
            code="XA123",
            title="Alpha extension",
            parent_code=None,
            is_extension=True,
            sort_key=100,
            chapter_or_group="X",
            raw_row_json={"Code": "XA123", "ClassKind": "extension"},
        ),
        SimpleTabulationCode(
            code="XT9",
            title="Theta extension",
            parent_code=None,
            is_extension=True,
            sort_key=30,
            chapter_or_group="X",
            raw_row_json={"Code": "XT9", "ClassKind": "extension"},
        ),
        SimpleTabulationCode(
            code="XY456",
            title="Psi extension",
            parent_code=None,
            is_extension=True,
            sort_key=40,
            chapter_or_group="X",
            raw_row_json={"Code": "XY456", "ClassKind": "extension"},
        ),
        SimpleTabulationCode(
            code="1A0Y",
            title="Other specified bacterial intestinal infections",
            parent_code="BLOCK-1",
            is_extension=False,
            sort_key=15,
            chapter_or_group="01",
            raw_row_json={
                "Code": "1A0Y",
                "ChapterNo": "01",
                "BlockId": "BLOCK-1",
                "ClassKind": "category",
            },
        ),
        SimpleTabulationCode(
            code="XN6BM",
            title="Staphylococcus aureus",
            parent_code=None,
            is_extension=True,
            sort_key=25,
            chapter_or_group="X",
            raw_row_json={"Code": "XN6BM", "ClassKind": "extension"},
        ),
        SimpleTabulationCode(
            code="MG51.00",
            title="Methicillin resistant Staphylococcus aureus",
            parent_code="BLOCK-1",
            is_extension=False,
            sort_key=30,
            chapter_or_group="01",
            raw_row_json={
                "Code": "MG51.00",
                "ChapterNo": "01",
                "BlockId": "BLOCK-1",
                "ClassKind": "category",
            },
        ),
    ]
    db_session.add_all(rows)
    db_session.commit()
    return rows
