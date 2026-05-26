import pytest

from app.api.schemas import NormalizeRequest


def test_normalize_request_defaults_ai_phrase_flags_to_false():
    payload = NormalizeRequest(codes=["ab12&cd34"])

    assert payload.codes == ["AB12&CD34"]
    assert payload.include_ai_phrase is False
    assert payload.run_ai_phrase is False


def test_normalize_request_rejects_both_ai_phrase_flags_true():
    with pytest.raises(ValueError, match="mutually exclusive"):
        NormalizeRequest(
            codes=["AB12"],
            include_ai_phrase=True,
            run_ai_phrase=True,
        )


def test_normalize_request_accepts_single_ai_phrase_flag():
    NormalizeRequest(codes=["AB12"], include_ai_phrase=True, run_ai_phrase=False)
    NormalizeRequest(codes=["AB12"], include_ai_phrase=False, run_ai_phrase=True)
