from sqlalchemy import select

from app.db.models import SimpleTabulationCode
from app.services.normalizer import CodeComponent
from app.core.config import get_settings
from app.services.ocl_sync import AUTO_DESCRIPTION_TEMPLATE, OCLSyncService


class FakeResponse:
    def __init__(self, status_code: int, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeOCLClient:
    def __init__(self, state, *args, **kwargs):
        self.state = state

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return None

    def get(self, url, headers=None):
        if url.endswith("/concepts/AB12%26CD34"):
            if self.state["concept_exists"]:
                return FakeResponse(
                    200,
                    {
                        "id": "AB12&CD34",
                        "concept_class": self.state.get("concept_class"),
                        "datatype": self.state.get("datatype"),
                        "extras": dict(self.state.get("extras", {})),
                    },
                )
            return FakeResponse(404, {})

        if url.endswith("/concepts/AB12%26CD34/names/"):
            return FakeResponse(200, list(self.state["names"]))

        if url.endswith("/concepts/AB12%26CD34/descriptions/"):
            return FakeResponse(200, list(self.state["descriptions"]))

        return FakeResponse(404, {})

    def post(self, url, json=None, headers=None):
        self.state["posts"].append({"url": url, "json": json})
        if url.endswith("/concepts/"):
            self.state["concept_exists"] = True
            self.state["concept_class"] = json.get("concept_class")
            self.state["datatype"] = json.get("datatype")
            self.state["extras"] = dict(json.get("extras", {}))
            self.state["names"] = list(json.get("names", []))
            return FakeResponse(201, {})

        if url.endswith("/names/"):
            payload = dict(json)
            payload["uuid"] = f"name-{len(self.state['names']) + 1}"
            self.state["names"].append(payload)
            return FakeResponse(201, payload)

        if url.endswith("/descriptions/"):
            payload = dict(json)
            payload["uuid"] = f"desc-{len(self.state['descriptions']) + 1}"
            self.state["descriptions"].append(payload)
            return FakeResponse(201, payload)

        return FakeResponse(404, {})

    def patch(self, url, json=None, headers=None):
        self.state["patches"].append({"url": url, "json": json})
        if url.endswith("/concepts/AB12%26CD34"):
            self.state["concept_class"] = json.get("concept_class", self.state.get("concept_class"))
            self.state["datatype"] = json.get("datatype", self.state.get("datatype"))
            self.state["extras"] = dict(json.get("extras", self.state.get("extras", {})))
            return FakeResponse(
                200,
                {
                    "id": "AB12&CD34",
                    "concept_class": self.state.get("concept_class"),
                    "datatype": self.state.get("datatype"),
                    "extras": dict(self.state.get("extras", {})),
                },
            )

        if "/names/" in url:
            uuid = url.rstrip("/").split("/")[-1]
            for item in self.state["names"]:
                if item.get("uuid") == uuid:
                    item.update(json)
                    return FakeResponse(200, item)

        if "/descriptions/" in url:
            uuid = url.rstrip("/").split("/")[-1]
            for item in self.state["descriptions"]:
                if item.get("uuid") == uuid:
                    item.update(json)
                    return FakeResponse(200, item)

        return FakeResponse(404, {})


def build_components():
    return [
        CodeComponent(
            code="AB12",
            separator=None,
            original_position=0,
            is_stem=True,
            is_extension=False,
        ),
        CodeComponent(
            code="CD34",
            separator="&",
            original_position=1,
            is_stem=False,
            is_extension=True,
        ),
    ]


def test_ocl_sync_creates_missing_concept_and_adds_synonym_and_description(
    monkeypatch,
    db_session,
    seeded_reference_data,
):
    monkeypatch.setenv("OCL_TOKEN", "ocl-token")
    monkeypatch.setenv("OCL_BASE_URL", "https://api.openconceptlab.org")
    monkeypatch.setenv(
        "OCL_LOOKUP_SOURCE",
        "/orgs/OpenMRS-OCL-Squad/sources/ICD-11-WHO-Mapper/",
    )
    get_settings.cache_clear()

    state = {
        "concept_exists": False,
        "concept_class": None,
        "datatype": None,
        "extras": {},
        "names": [],
        "descriptions": [],
        "posts": [],
        "patches": [],
    }
    service = OCLSyncService(
        session=db_session,
        client_factory=lambda *args, **kwargs: FakeOCLClient(state),
    )

    synced = service.sync_normalized_result(
        normalized_code="AB12&CD34",
        title="Alpha condition [Delta qualifier]",
        ai_phrase="Alpha condition with delta qualifier",
        ai_model_name="google/gemini-test",
        components=build_components(),
    )

    assert synced is True
    assert state["posts"][0]["url"].endswith("/concepts/")
    assert state["posts"][0]["json"] == {
        "id": "AB12&CD34",
        "concept_class": "Diagnosis",
        "datatype": "N/A",
        "retired": False,
        "extras": {"isLeaf": True, "ChapterNo": "01", "BlockId": "BLOCK-1"},
        "names": [
            {
                "name": "Alpha condition [Delta qualifier]",
                "locale": "en",
                "locale_preferred": True,
                "name_type": "FULLY_SPECIFIED",
            }
        ],
    }
    assert state["posts"][1]["json"] == {
        "name": "Alpha condition with delta qualifier",
        "locale": "en",
        "locale_preferred": False,
        "name_type": None,
    }
    assert state["posts"][2]["json"] == {
        "description": AUTO_DESCRIPTION_TEMPLATE.format(
            model_name="google/gemini-test"
        ),
        "locale": "en",
        "locale_preferred": False,
    }
    assert state["patches"] == []


def test_ocl_sync_updates_existing_concept_metadata_title_synonym_and_description(
    monkeypatch,
    db_session,
    seeded_reference_data,
):
    monkeypatch.setenv("OCL_TOKEN", "ocl-token")
    monkeypatch.setenv("OCL_BASE_URL", "https://api.openconceptlab.org")
    monkeypatch.setenv(
        "OCL_LOOKUP_SOURCE",
        "/orgs/OpenMRS-OCL-Squad/sources/ICD-11-WHO-Mapper/",
    )
    get_settings.cache_clear()

    stem = db_session.scalar(
        select(SimpleTabulationCode).where(SimpleTabulationCode.code == "AB12")
    )
    stem.raw_row_json["BlockId"] = None
    db_session.commit()

    state = {
        "concept_exists": True,
        "concept_class": "Misc",
        "datatype": "Text",
        "extras": {"isLeaf": False},
        "names": [
            {
                "uuid": "name-fsn",
                "name": "Old title",
                "locale": "en",
                "locale_preferred": True,
                "name_type": "FULLY_SPECIFIED",
                "type": "ConceptName",
            },
            {
                "uuid": "name-syn",
                "name": "Old synonym",
                "locale": "en",
                "locale_preferred": False,
                "name_type": None,
                "type": "ConceptName",
            }
        ],
        "descriptions": [
            {
                "uuid": "desc-1",
                "description": AUTO_DESCRIPTION_TEMPLATE.format(model_name="old-model"),
                "locale": "en",
                "locale_preferred": False,
            }
        ],
        "posts": [],
        "patches": [],
    }
    service = OCLSyncService(
        session=db_session,
        client_factory=lambda *args, **kwargs: FakeOCLClient(state),
    )

    synced = service.sync_normalized_result(
        normalized_code="AB12&CD34",
        title="New title [New qualifier]",
        ai_phrase="New synonym",
        ai_model_name="new-model",
        components=build_components(),
    )

    assert synced is True
    assert state["posts"] == []
    assert state["patches"][0]["url"].endswith("/concepts/AB12%26CD34")
    assert state["patches"][0]["json"] == {
        "concept_class": "Diagnosis",
        "datatype": "N/A",
        "extras": {"isLeaf": True, "ChapterNo": "01", "BlockId": "BLOCK-1"},
    }
    assert "/names/name-fsn/" in state["patches"][1]["url"]
    assert "/names/name-syn/" in state["patches"][2]["url"]
    assert "/descriptions/desc-1/" in state["patches"][3]["url"]
    assert state["concept_class"] == "Diagnosis"
    assert state["datatype"] == "N/A"
    assert state["extras"] == {"isLeaf": True, "ChapterNo": "01", "BlockId": "BLOCK-1"}
    assert state["names"][0]["name"] == "New title [New qualifier]"
    assert state["names"][1]["name"] == "New synonym"
    assert state["descriptions"][0]["description"] == AUTO_DESCRIPTION_TEMPLATE.format(
        model_name="new-model"
    )
