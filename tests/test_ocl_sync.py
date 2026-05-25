from urllib.parse import quote

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import SimpleTabulationCode
from app.services.normalizer import CodeComponent
from app.services.ocl_sync import AUTO_DESCRIPTION_TEMPLATE, OCLSyncService


NORMALIZED_CODE = "AB12&CD34"
LOOKUP_SOURCE = "/orgs/OpenMRS-OCL-Squad/sources/ICD-11-WHO-Mapper/"
CONCEPT_REFERENCE_URL = f"{LOOKUP_SOURCE}concepts/{quote(NORMALIZED_CODE, safe='')}/"
WHO_TARGET_URL = "/orgs/WHO/sources/ICD-11-WHO/concepts/AB12/"
CONCEPT_ENDPOINT_SUFFIX = f"/concepts/{quote(quote(NORMALIZED_CODE, safe=''), safe='')}/"
CONCEPT_NAMES_SUFFIX = f"{CONCEPT_ENDPOINT_SUFFIX}names/"
CONCEPT_DESCRIPTIONS_SUFFIX = f"{CONCEPT_ENDPOINT_SUFFIX}descriptions/"
CONCEPT_MAPPINGS_SUFFIX = f"{CONCEPT_ENDPOINT_SUFFIX}mappings/"
SOURCE_MAPPINGS_SUFFIX = f"{LOOKUP_SOURCE.rstrip('/')}/mappings/"


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
        if url.endswith(CONCEPT_ENDPOINT_SUFFIX):
            if self.state["concept_exists"]:
                return FakeResponse(
                    200,
                    {
                        "id": NORMALIZED_CODE,
                        "concept_class": self.state.get("concept_class"),
                        "datatype": self.state.get("datatype"),
                        "extras": dict(self.state.get("extras", {})),
                    },
                )
            return FakeResponse(404, {})

        if url.endswith(CONCEPT_NAMES_SUFFIX):
            return FakeResponse(200, list(self.state["names"]))

        if url.endswith(CONCEPT_DESCRIPTIONS_SUFFIX):
            return FakeResponse(200, list(self.state["descriptions"]))

        if url.endswith(CONCEPT_MAPPINGS_SUFFIX):
            return FakeResponse(200, list(self.state["mappings"]))

        return FakeResponse(404, {})

    def post(self, url, json=None, headers=None):
        self.state["posts"].append({"url": url, "json": json})
        if url.endswith("/concepts/"):
            self.state["concept_exists"] = True
            self.state["concept_class"] = json.get("concept_class")
            self.state["datatype"] = json.get("datatype")
            self.state["extras"] = dict(json.get("extras", {}))
            self.state["names"] = [dict(item) for item in json.get("names", [])]
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

        if "/concepts/" not in url and url.endswith("/mappings/"):
            payload = dict(json)
            payload["id"] = f"mapping-{len(self.state['mappings']) + 1}"
            payload["url"] = f"{url}{payload['id']}/"
            self.state["mappings"].append(payload)
            return FakeResponse(201, payload)

        return FakeResponse(404, {})

    def patch(self, url, json=None, headers=None):
        self.state["patches"].append({"url": url, "json": json})
        if url.endswith(CONCEPT_ENDPOINT_SUFFIX):
            self.state["concept_class"] = json.get("concept_class", self.state.get("concept_class"))
            self.state["datatype"] = json.get("datatype", self.state.get("datatype"))
            self.state["extras"] = dict(json.get("extras", self.state.get("extras", {})))
            return FakeResponse(
                200,
                {
                    "id": NORMALIZED_CODE,
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

        if "/mappings/" in url:
            mapping_id = url.rstrip("/").split("/")[-1]
            for item in self.state["mappings"]:
                if item.get("id") == mapping_id:
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


def expected_extras():
    return {
        "isLeaf": True,
        "Foundation URI": "http://foundation.example/AB12",
        "Linearization URI": "http://linearization.example/AB12",
        "DepthInKind": "2",
        "IsResidual": "False",
        "BrowserLink": "https://browser.example/AB12",
        "ChapterNo": "01",
        "BlockId": "BLOCK-1",
    }


def test_ocl_sync_creates_missing_concept_and_adds_synonym_description_and_mapping(
    monkeypatch,
    db_session,
    seeded_reference_data,
):
    monkeypatch.setenv("OCL_TOKEN", "ocl-token")
    monkeypatch.setenv("OCL_BASE_URL", "https://api.openconceptlab.org")
    monkeypatch.setenv("OCL_LOOKUP_SOURCE", LOOKUP_SOURCE)
    get_settings.cache_clear()

    state = {
        "concept_exists": False,
        "concept_class": None,
        "datatype": None,
        "extras": {},
        "names": [],
        "descriptions": [],
        "mappings": [],
        "posts": [],
        "patches": [],
    }
    service = OCLSyncService(
        session=db_session,
        client_factory=lambda *args, **kwargs: FakeOCLClient(state),
    )

    synced = service.sync_normalized_result(
        normalized_code=NORMALIZED_CODE,
        title="Alpha condition [Delta qualifier]",
        ai_phrase="Alpha condition with delta qualifier",
        ai_model_name="google/gemini-test",
        components=build_components(),
    )

    assert synced is True
    assert state["posts"][0]["url"].endswith("/concepts/")
    assert state["posts"][0]["json"] == {
        "id": NORMALIZED_CODE,
        "concept_class": "Diagnosis",
        "datatype": "N/A",
        "retired": False,
        "extras": expected_extras(),
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
    }
    assert state["posts"][2]["json"] == {
        "description": AUTO_DESCRIPTION_TEMPLATE.format(
            model_name="google/gemini-test"
        ),
        "locale": "en",
        "locale_preferred": False,
    }
    assert state["posts"][3]["json"] == {
        "map_type": "NARROWER-THAN",
        "from_concept_url": CONCEPT_REFERENCE_URL,
        "to_concept_url": WHO_TARGET_URL,
    }
    assert state["patches"] == []


def test_ocl_sync_updates_existing_concept_metadata_title_synonym_description_and_mapping(
    monkeypatch,
    db_session,
    seeded_reference_data,
):
    monkeypatch.setenv("OCL_TOKEN", "ocl-token")
    monkeypatch.setenv("OCL_BASE_URL", "https://api.openconceptlab.org")
    monkeypatch.setenv("OCL_LOOKUP_SOURCE", LOOKUP_SOURCE)
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
            },
        ],
        "descriptions": [
            {
                "uuid": "desc-1",
                "description": AUTO_DESCRIPTION_TEMPLATE.format(model_name="old-model"),
                "locale": "en",
                "locale_preferred": False,
            }
        ],
        "mappings": [
            {
                "id": "mapping-1",
                "url": f"https://api.openconceptlab.org{SOURCE_MAPPINGS_SUFFIX}mapping-1/",
                "map_type": "NARROWER-THAN",
                "from_concept_url": CONCEPT_REFERENCE_URL,
                "to_concept_url": "/orgs/WHO/sources/ICD-11-WHO/concepts/EF56/",
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
        normalized_code=NORMALIZED_CODE,
        title="New title [New qualifier]",
        ai_phrase="New synonym",
        ai_model_name="new-model",
        components=build_components(),
    )

    assert synced is True
    assert state["posts"] == []
    assert state["patches"][0]["url"].endswith(CONCEPT_ENDPOINT_SUFFIX)
    assert state["patches"][0]["json"] == {
        "concept_class": "Diagnosis",
        "datatype": "N/A",
        "extras": expected_extras(),
    }
    assert "/names/name-fsn/" in state["patches"][1]["url"]
    assert "/names/name-syn/" in state["patches"][2]["url"]
    assert "/descriptions/desc-1/" in state["patches"][3]["url"]
    assert state["patches"][4]["url"].endswith("/mappings/mapping-1/")
    assert state["patches"][4]["json"] == {
        "map_type": "NARROWER-THAN",
        "from_concept_url": CONCEPT_REFERENCE_URL,
        "to_concept_url": WHO_TARGET_URL,
    }
    assert state["concept_class"] == "Diagnosis"
    assert state["datatype"] == "N/A"
    assert state["extras"] == expected_extras()
    assert state["names"][0]["name"] == "New title [New qualifier]"
    assert state["names"][1]["name"] == "New synonym"
    assert state["descriptions"][0]["description"] == AUTO_DESCRIPTION_TEMPLATE.format(
        model_name="new-model"
    )
    assert state["mappings"][0]["to_concept_url"] == WHO_TARGET_URL


def test_ocl_sync_marks_non_leaf_stem_with_is_leaf_false(
    monkeypatch,
    db_session,
    seeded_reference_data,
):
    # BLOCK-1 has children in the fixture (AB12, EF56, 1A0Y, MG51.00), so the
    # concept payload sent to OCL must report ``isLeaf: False``.
    monkeypatch.setenv("OCL_TOKEN", "ocl-token")
    monkeypatch.setenv("OCL_BASE_URL", "https://api.openconceptlab.org")
    monkeypatch.setenv("OCL_LOOKUP_SOURCE", LOOKUP_SOURCE)
    get_settings.cache_clear()

    state = {
        "concept_exists": False,
        "concept_class": None,
        "datatype": None,
        "extras": {},
        "names": [],
        "descriptions": [],
        "mappings": [],
        "posts": [],
        "patches": [],
    }
    service = OCLSyncService(
        session=db_session,
        client_factory=lambda *args, **kwargs: FakeOCLClient(state),
    )

    synced = service.sync_normalized_result(
        normalized_code="BLOCK-1",
        title="Block One",
        ai_phrase=None,
        ai_model_name="google/gemini-test",
        components=[
            CodeComponent(
                code="BLOCK-1",
                separator=None,
                original_position=0,
                is_stem=True,
                is_extension=False,
            ),
        ],
    )

    assert synced is True
    assert state["posts"][0]["json"]["extras"]["isLeaf"] is False


def test_sync_concept_skeleton_creates_concept_fsn_and_mapping_without_synonym_or_description(
    monkeypatch,
    db_session,
    seeded_reference_data,
):
    monkeypatch.setenv("OCL_TOKEN", "ocl-token")
    monkeypatch.setenv("OCL_BASE_URL", "https://api.openconceptlab.org")
    monkeypatch.setenv("OCL_LOOKUP_SOURCE", LOOKUP_SOURCE)
    get_settings.cache_clear()

    state = {
        "concept_exists": False,
        "concept_class": None,
        "datatype": None,
        "extras": {},
        "names": [],
        "descriptions": [],
        "mappings": [],
        "posts": [],
        "patches": [],
    }
    service = OCLSyncService(
        session=db_session,
        client_factory=lambda *args, **kwargs: FakeOCLClient(state),
    )

    synced = service.sync_concept_skeleton(
        normalized_code=NORMALIZED_CODE,
        title="Alpha condition [Delta qualifier]",
        components=build_components(),
    )

    assert synced is True
    post_urls = [post["url"] for post in state["posts"]]
    assert any(url.endswith("/concepts/") for url in post_urls)
    assert any(url.endswith(SOURCE_MAPPINGS_SUFFIX) for url in post_urls)
    assert not any(url.endswith(CONCEPT_DESCRIPTIONS_SUFFIX) for url in post_urls)
    # No synonym POST: the FSN is created together with the concept payload,
    # and no other /names/ POST should happen during the skeleton phase.
    assert not any(url.endswith(CONCEPT_NAMES_SUFFIX) for url in post_urls)
    assert state["descriptions"] == []
    # Only the FSN was attached to the concept payload.
    assert len(state["names"]) == 1
    assert state["names"][0]["name_type"] == "FULLY_SPECIFIED"


def test_sync_ai_enrichment_adds_synonym_and_description_to_existing_concept(
    monkeypatch,
    db_session,
    seeded_reference_data,
):
    monkeypatch.setenv("OCL_TOKEN", "ocl-token")
    monkeypatch.setenv("OCL_BASE_URL", "https://api.openconceptlab.org")
    monkeypatch.setenv("OCL_LOOKUP_SOURCE", LOOKUP_SOURCE)
    get_settings.cache_clear()

    state = {
        "concept_exists": True,
        "concept_class": "Diagnosis",
        "datatype": "N/A",
        "extras": dict(expected_extras()),
        "names": [
            {
                "uuid": "name-fsn",
                "name": "Alpha condition [Delta qualifier]",
                "locale": "en",
                "locale_preferred": True,
                "name_type": "FULLY_SPECIFIED",
                "type": "ConceptName",
            }
        ],
        "descriptions": [],
        "mappings": [],
        "posts": [],
        "patches": [],
    }
    service = OCLSyncService(
        session=db_session,
        client_factory=lambda *args, **kwargs: FakeOCLClient(state),
    )

    synced = service.sync_ai_enrichment(
        normalized_code=NORMALIZED_CODE,
        title="Alpha condition [Delta qualifier]",
        ai_phrase="Alpha condition with delta qualifier",
        ai_model_name="google/gemini-test",
    )

    assert synced is True
    post_urls = [post["url"] for post in state["posts"]]
    assert any(url.endswith(CONCEPT_NAMES_SUFFIX) for url in post_urls)
    assert any(url.endswith(CONCEPT_DESCRIPTIONS_SUFFIX) for url in post_urls)
    # Enrichment must not touch the concept itself or the mappings endpoint.
    assert not any(url.endswith("/concepts/") for url in post_urls)
    assert not any(url.endswith(SOURCE_MAPPINGS_SUFFIX) for url in post_urls)
    assert state["patches"] == []
    synonym = next(name for name in state["names"] if name["uuid"] != "name-fsn")
    assert synonym["name"] == "Alpha condition with delta qualifier"
    assert state["descriptions"][0]["description"] == AUTO_DESCRIPTION_TEMPLATE.format(
        model_name="google/gemini-test"
    )


def test_sync_ai_enrichment_skips_when_phrase_matches_title(
    monkeypatch,
    db_session,
    seeded_reference_data,
):
    monkeypatch.setenv("OCL_TOKEN", "ocl-token")
    monkeypatch.setenv("OCL_BASE_URL", "https://api.openconceptlab.org")
    monkeypatch.setenv("OCL_LOOKUP_SOURCE", LOOKUP_SOURCE)
    get_settings.cache_clear()

    state = {
        "concept_exists": True,
        "concept_class": "Diagnosis",
        "datatype": "N/A",
        "extras": {},
        "names": [],
        "descriptions": [],
        "mappings": [],
        "posts": [],
        "patches": [],
    }
    service = OCLSyncService(
        session=db_session,
        client_factory=lambda *args, **kwargs: FakeOCLClient(state),
    )

    synced = service.sync_ai_enrichment(
        normalized_code=NORMALIZED_CODE,
        title="Same phrase",
        ai_phrase="Same phrase",
        ai_model_name="m",
    )

    assert synced is False
    assert state["posts"] == []
    assert state["patches"] == []
