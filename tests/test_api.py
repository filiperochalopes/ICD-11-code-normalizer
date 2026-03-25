from fastapi.testclient import TestClient

from app.db.models import NormalizedResult
from app.main import app


def test_normalize_requires_bearer_token(db_session, seeded_reference_data):
    with TestClient(app) as client:
        response = client.post(
            "/normalize",
            json={"codes": ["AB12&CD34"], "include_ai_phrase": False},
        )

    assert response.status_code == 401


def test_normalize_returns_normalized_codes_and_titles(db_session, seeded_reference_data):
    with TestClient(app) as client:
        response = client.post(
            "/normalize",
            headers={"Authorization": "Bearer test-token"},
            json={
                "codes": ["XA123&XY456/XT9", "AB12&CD34"],
                "include_ai_phrase": False,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["results"] == [
        {
            "input_code": "XA123&XY456/XT9",
            "normalized_code": "XA123/XT9&XY456",
            "title": "Alpha extension / Theta extension + Psi extension",
            "ai_phrase": None,
            "from_cache": False,
        },
        {
            "input_code": "AB12&CD34",
            "normalized_code": "AB12&CD34",
            "title": "Alpha condition + Delta qualifier",
            "ai_phrase": None,
            "from_cache": False,
        },
    ]

    stored_result = db_session.query(NormalizedResult).filter_by(normalized_code="AB12&CD34").one()
    assert stored_result.title == "Alpha condition + Delta qualifier"
    assert stored_result.ai_phrase is None
