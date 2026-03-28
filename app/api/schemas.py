from pydantic import BaseModel, Field, field_validator


class NormalizeRequest(BaseModel):
    codes: list[str] = Field(..., min_length=1)
    include_ai_phrase: bool = True

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


class NormalizeResultItem(BaseModel):
    input_code: str
    normalized_code: str
    title: str
    ai_phrase: str | None
    from_cache: bool


class NormalizeResponse(BaseModel):
    results: list[NormalizeResultItem]
