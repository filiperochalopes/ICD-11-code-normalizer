from app.services.cache import CacheService
from app.services.normalizer import NormalizerService
from app.services.title_builder import TitleBuilderService


def test_normalizer_sorts_stem_groups_and_keeps_extension_attached_to_original_stem(
    db_session,
    seeded_reference_data,
):
    service = NormalizerService(db_session)
    result = service.normalize("AB12&CD34/EF56")

    assert result.normalized_code == "EF56/AB12&CD34"
    assert [component.code for component in result.components] == ["EF56", "AB12", "CD34"]
    assert [component.is_stem for component in result.components] == [True, True, False]


def test_normalizer_sorts_extensions_only_inside_their_own_stem_group(
    db_session,
    seeded_reference_data,
):
    service = NormalizerService(db_session)
    result = service.normalize("AB12&XY456&XT9")

    assert result.normalized_code == "AB12&XT9&XY456"
    assert [component.code for component in result.components] == ["AB12", "XT9", "XY456"]
    assert [component.is_stem for component in result.components] == [True, False, False]


def test_cache_service_reuses_matching_generated_result(db_session):
    cache = CacheService(db_session)
    cache.store_cached_result(
        input_code="AB12&CD34",
        normalized_code="AB12&CD34",
        include_ai_phrase=True,
        title="Alpha condition [Delta qualifier]",
        ai_phrase="Alpha condition with delta qualifier",
        model_name="openrouter/free",
        prompt_version="v1",
    )
    db_session.commit()

    cached = cache.get_cached_result(
        normalized_code="AB12&CD34",
        title="Alpha condition [Delta qualifier]",
        include_ai_phrase=True,
        model_name="openrouter/free",
        prompt_version="v1",
    )

    assert cached is not None
    assert cached.ai_phrase == "Alpha condition with delta qualifier"


def test_title_builder_uses_deterministic_joiners(db_session, seeded_reference_data):
    service = NormalizerService(db_session)
    result = service.normalize("1A0Y&XN6BM/MG51.00")
    title = TitleBuilderService().build_title(result.components)

    assert (
        title
        == "Other specified bacterial intestinal infections [Staphylococcus aureus] / "
        "Methicillin resistant Staphylococcus aureus"
    )
