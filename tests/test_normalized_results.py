from sqlalchemy import select

from app.db.models import NormalizedResult
from app.services.results_store import NormalizedResultsService


def test_normalized_results_service_backfills_ai_phrase_without_creating_a_new_row(
    db_session,
):
    service = NormalizedResultsService(db_session)

    service.upsert_result(
        normalized_code="AB12&CD34",
        title="Alpha condition + Delta qualifier",
        ai_phrase=None,
    )
    db_session.commit()

    service.upsert_result(
        normalized_code="AB12&CD34",
        title="Alpha condition + Delta qualifier",
        ai_phrase="Alpha condition with delta qualifier",
    )
    db_session.commit()

    stored_rows = db_session.scalars(select(NormalizedResult)).all()

    assert len(stored_rows) == 1
    assert stored_rows[0].normalized_code == "AB12&CD34"
    assert stored_rows[0].title == "Alpha condition + Delta qualifier"
    assert stored_rows[0].ai_phrase == "Alpha condition with delta qualifier"
