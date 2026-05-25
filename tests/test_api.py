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
                "codes": ["AB12&CD34/EF56", "1A0Y&XN6BM/MG51.00"],
                "include_ai_phrase": False,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["results"] == [
        {
            "input_code": "AB12&CD34/EF56",
            "normalized_code": "EF56/AB12&CD34",
            "title": "Echo disorder / Alpha condition [Delta qualifier]",
            "ai_phrase": None,
            "from_cache": False,
        },
        {
            "input_code": "1A0Y&XN6BM/MG51.00",
            "normalized_code": "1A0Y&XN6BM/MG51.00",
            "title": (
                "Other specified bacterial intestinal infections "
                "[Staphylococcus aureus] / Methicillin resistant Staphylococcus aureus"
            ),
            "ai_phrase": None,
            "from_cache": False,
        },
    ]

    stored_result = db_session.query(NormalizedResult).filter_by(normalized_code="EF56/AB12&CD34").one()
    assert stored_result.title == "Echo disorder / Alpha condition [Delta qualifier]"
    assert stored_result.ai_phrase is None


def test_normalize_triggers_ocl_sync(monkeypatch, db_session, seeded_reference_data):
    skeleton_calls = []
    enrichment_calls = []
    full_sync_calls = []

    def fake_skeleton(self, normalized_code, title, components=None):
        skeleton_calls.append(
            {
                "normalized_code": normalized_code,
                "title": title,
                "components": [component.code for component in components or []],
            }
        )
        return True

    def fake_enrichment(self, normalized_code, title, ai_phrase, ai_model_name=None):
        enrichment_calls.append(
            {
                "normalized_code": normalized_code,
                "title": title,
                "ai_phrase": ai_phrase,
                "ai_model_name": ai_model_name,
            }
        )
        return True

    def fake_full_sync(
        self,
        normalized_code,
        title,
        ai_phrase=None,
        ai_model_name=None,
        components=None,
    ):
        full_sync_calls.append(normalized_code)
        return True

    monkeypatch.setattr(
        "app.api.routes.OCLSyncService.sync_concept_skeleton", fake_skeleton
    )
    monkeypatch.setattr(
        "app.api.routes.OCLSyncService.sync_ai_enrichment", fake_enrichment
    )
    monkeypatch.setattr(
        "app.api.routes.OCLSyncService.sync_normalized_result", fake_full_sync
    )

    with TestClient(app) as client:
        response = client.post(
            "/normalize",
            headers={"Authorization": "Bearer test-token"},
            json={"codes": ["AB12&CD34"], "include_ai_phrase": False},
        )

    assert response.status_code == 200
    # With include_ai_phrase=False we publish the skeleton immediately and skip
    # the enrichment phase (no ai_phrase to add).
    assert skeleton_calls == [
        {
            "normalized_code": "AB12&CD34",
            "title": "Alpha condition [Delta qualifier]",
            "components": ["AB12", "CD34"],
        }
    ]
    assert enrichment_calls == []
    assert full_sync_calls == []


def test_normalize_skips_ai_phrase_for_non_postcoordinated_codes(
    monkeypatch,
    db_session,
    seeded_reference_data,
):
    def fail_if_called(self, normalized_code, components, basic_title):
        raise AssertionError("generate_ai_phrase should not be called for non post-coordinated codes")

    monkeypatch.setattr("app.api.routes.AIPhraseService.generate_ai_phrase", fail_if_called)

    with TestClient(app) as client:
        response = client.post(
            "/normalize",
            headers={"Authorization": "Bearer test-token"},
            json={"codes": ["AB12"], "include_ai_phrase": True},
        )

    assert response.status_code == 200
    assert response.json()["results"] == [
        {
            "input_code": "AB12",
            "normalized_code": "AB12",
            "title": "Alpha condition",
            "ai_phrase": None,
            "from_cache": False,
        }
    ]
