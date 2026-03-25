from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import NormalizedResult


class NormalizedResultsService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_result(
        self,
        normalized_code: str,
        title: str,
        ai_phrase: str | None = None,
    ) -> NormalizedResult:
        existing = self.session.scalar(
            select(NormalizedResult).where(
                NormalizedResult.normalized_code == normalized_code
            )
        )

        if existing:
            existing.title = title
            if ai_phrase is not None:
                existing.ai_phrase = ai_phrase
            self.session.flush()
            return existing

        normalized_result = NormalizedResult(
            normalized_code=normalized_code,
            title=title,
            ai_phrase=ai_phrase,
        )
        self.session.add(normalized_result)
        self.session.flush()
        return normalized_result
