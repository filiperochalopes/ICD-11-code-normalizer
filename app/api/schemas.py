from pydantic import BaseModel, Field, field_validator, model_validator


class NormalizeRequest(BaseModel):
    codes: list[str] = Field(..., min_length=1)
    # When True, the LLM runs synchronously and ``ai_phrase`` is populated in
    # the response.
    include_ai_phrase: bool = False
    # When True, the LLM runs in a FastAPI background task after the response
    # is returned. ``ai_phrase`` is NOT included in the response, but the cache
    # and OCL enrichment are persisted asynchronously. Mutually exclusive with
    # ``include_ai_phrase`` — only one of the two may be True per request.
    run_ai_phrase: bool = False

    @field_validator("codes")
    @classmethod
    def validate_codes(cls, value: list[str]) -> list[str]:
        normalized_codes: list[str] = []
        for item in value:
            cleaned = item.strip().upper()
            if not cleaned:
                raise ValueError("codes must not contain empty values")
            normalized_codes.append(cleaned)
        return normalized_codes

    @model_validator(mode="after")
    def _ai_phrase_flags_are_exclusive(self) -> "NormalizeRequest":
        if self.include_ai_phrase and self.run_ai_phrase:
            raise ValueError(
                "include_ai_phrase and run_ai_phrase are mutually exclusive — "
                "set only one of them to true"
            )
        return self


class NormalizeResultItem(BaseModel):
    input_code: str
    normalized_code: str
    title: str
    ai_phrase: str | None
    from_cache: bool


class NormalizeResponse(BaseModel):
    results: list[NormalizeResultItem]
