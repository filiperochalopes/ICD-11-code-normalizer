import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import NormalizeRequest, NormalizeResponse, NormalizeResultItem
from app.core.auth import require_bearer_token
from app.db.session import get_db_session
from app.services.ai_phrase import AIPhraseService
from app.services.cache import CacheService
from app.services.normalizer import NormalizationError, NormalizerService
from app.services.ocl_sync import OCLSyncService
from app.services.results_store import NormalizedResultsService
from app.services.title_builder import TitleBuilderService


logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/normalize",
    response_model=NormalizeResponse,
    dependencies=[Depends(require_bearer_token)],
)
def normalize_codes(
    payload: NormalizeRequest,
    db: Annotated[Session, Depends(get_db_session)],
) -> NormalizeResponse:
    normalizer = NormalizerService(db)
    title_builder = TitleBuilderService()
    cache_service = CacheService(db)
    ai_service = AIPhraseService()
    ocl_sync_service = OCLSyncService(db)
    normalized_results_service = NormalizedResultsService(db)

    results: list[NormalizeResultItem] = []

    for input_code in payload.codes:
        try:
            normalization_result = normalizer.normalize(input_code)
            title = title_builder.build_title(normalization_result.components)

            ai_phrase: str | None = None
            ai_model_name: str | None = None
            from_cache = False

            if payload.include_ai_phrase and ai_service.should_generate_for_code(
                normalization_result.normalized_code
            ):
                cached = cache_service.get_cached_result(
                    normalized_code=normalization_result.normalized_code,
                    title=title,
                    include_ai_phrase=True,
                    model_name=ai_service.model_name,
                    prompt_version=ai_service.prompt_version,
                )
                if cached and cached.ai_phrase:
                    ai_phrase = cached.ai_phrase
                    ai_model_name = cached.resolved_model_name or cached.model_name
                    from_cache = True
                else:
                    ai_result = ai_service.generate_ai_phrase(
                        normalized_code=normalization_result.normalized_code,
                        components=normalization_result.components,
                        basic_title=title,
                    )
                    if ai_result:
                        ai_phrase = ai_result.text
                        ai_model_name = ai_result.resolved_model_name
                        cache_service.store_cached_result(
                            input_code=input_code,
                            normalized_code=normalization_result.normalized_code,
                            include_ai_phrase=True,
                            title=title,
                            ai_phrase=ai_phrase,
                            model_name=ai_result.requested_model_name,
                            prompt_version=ai_service.prompt_version,
                            resolved_model_name=ai_result.resolved_model_name,
                        )

            normalized_results_service.upsert_result(
                normalized_code=normalization_result.normalized_code,
                title=title,
                ai_phrase=ai_phrase,
            )
            db.commit()
            ocl_sync_service.sync_normalized_result(
                normalized_code=normalization_result.normalized_code,
                title=title,
                ai_phrase=ai_phrase,
                ai_model_name=ai_model_name,
                components=normalization_result.components,
            )

            results.append(
                NormalizeResultItem(
                    input_code=input_code,
                    normalized_code=normalization_result.normalized_code,
                    title=title,
                    ai_phrase=ai_phrase,
                    from_cache=from_cache,
                )
            )
        except NormalizationError:
            logger.exception("Parsing error while normalizing code: %s", input_code)
            db.rollback()
            results.append(
                NormalizeResultItem(
                    input_code=input_code,
                    normalized_code=input_code.strip().upper(),
                    title=f"Unable to parse ICD-11 expression: {input_code.strip().upper()}",
                    ai_phrase=None,
                    from_cache=False,
                )
            )

    return NormalizeResponse(results=results)
