from app.api.schemas import NormalizeRequest


def test_normalize_request_defaults_include_ai_phrase_to_true():
    payload = NormalizeRequest(codes=["ab12&cd34"])

    assert payload.codes == ["AB12&CD34"]
    assert payload.include_ai_phrase is True
