from app.services.cache import CacheService
from app.services.normalizer import NormalizerService
from app.services.title_builder import TitleBuilderService


def test_normalizer_sorts_trailing_components_using_simple_tabulation_order(
    db_session,
    seeded_reference_data,
):
    service = NormalizerService(db_session)
    result = service.normalize("XA123&XY456/XT9")

    assert result.normalized_code == "XA123/XT9&XY456"
    assert [component.code for component in result.components] == ["XA123", "XT9", "XY456"]


def test_cache_service_reuses_matching_generated_result(db_session):
    cache = CacheService(db_session)
    cache.store_cached_result(
        input_code="AB12&CD34",
        normalized_code="AB12&CD34",
        include_ai_phrase=True,
        title="Alpha condition + Delta qualifier",
        ai_phrase="Alpha condition with delta qualifier",
        model_name="openrouter/free",
        prompt_version="v1",
    )
    db_session.commit()

    cached = cache.get_cached_result(
        normalized_code="AB12&CD34",
        title="Alpha condition + Delta qualifier",
        include_ai_phrase=True,
        model_name="openrouter/free",
        prompt_version="v1",
    )

    assert cached is not None
    assert cached.ai_phrase == "Alpha condition with delta qualifier"


def test_title_builder_uses_deterministic_joiners(db_session, seeded_reference_data):
    service = NormalizerService(db_session)
    result = service.normalize("XA123&XY456/XT9")
    title = TitleBuilderService().build_title(result.components)

    assert title == "Alpha extension / Theta extension + Psi extension"

