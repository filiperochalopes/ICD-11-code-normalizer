import hashlib
import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GeneratedCache


logger = logging.getLogger(__name__)


class CacheService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_cached_result(
        self,
        normalized_code: str,
        title: str,
        include_ai_phrase: bool,
        model_name: str,
        prompt_version: str,
    ) -> GeneratedCache | None:
        if not include_ai_phrase:
            return None

        response_hash = self.build_response_hash(
            normalized_code=normalized_code,
            title=title,
            include_ai_phrase=include_ai_phrase,
            model_name=model_name,
            prompt_version=prompt_version,
        )
        cached = self.session.scalar(
            select(GeneratedCache).where(GeneratedCache.response_hash == response_hash)
        )
        logger.info(
            "Cache %s for normalized_code=%s",
            "hit" if cached else "miss",
            normalized_code,
        )
        return cached

    def store_cached_result(
        self,
        input_code: str,
        normalized_code: str,
        include_ai_phrase: bool,
        title: str,
        ai_phrase: str,
        model_name: str,
        prompt_version: str,
        resolved_model_name: str | None = None,
    ) -> GeneratedCache:
        response_hash = self.build_response_hash(
            normalized_code=normalized_code,
            title=title,
            include_ai_phrase=include_ai_phrase,
            model_name=model_name,
            prompt_version=prompt_version,
        )

        existing = self.session.scalar(
            select(GeneratedCache).where(GeneratedCache.response_hash == response_hash)
        )
        if existing:
            return existing

        cached = GeneratedCache(
            input_code=input_code,
            normalized_code=normalized_code,
            include_ai_phrase=include_ai_phrase,
            title=title,
            ai_phrase=ai_phrase,
            prompt_version=prompt_version,
            model_name=model_name,
            resolved_model_name=resolved_model_name,
            response_hash=response_hash,
        )
        self.session.add(cached)
        self.session.flush()
        return cached

    @staticmethod
    def build_response_hash(
        normalized_code: str,
        title: str,
        include_ai_phrase: bool,
        model_name: str,
        prompt_version: str,
    ) -> str:
        payload = json.dumps(
            {
                "normalized_code": normalized_code,
                "title": title,
                "include_ai_phrase": include_ai_phrase,
                "model_name": model_name,
                "prompt_version": prompt_version,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
