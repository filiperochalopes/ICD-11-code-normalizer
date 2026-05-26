import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.api.schemas import NormalizeRequest, NormalizeResponse, NormalizeResultItem
from app.core.auth import require_bearer_token
from app.db.session import get_db_session, get_session_factory
from app.services.ai_phrase import AIPhraseService
from app.services.cache import CacheService
from app.services.normalizer import CodeComponent, NormalizationError, NormalizerService
from app.services.ocl_sync import OCLSyncService
from app.services.results_store import NormalizedResultsService
from app.services.title_builder import TitleBuilderService


logger = logging.getLogger(__name__)

router = APIRouter()


def _run_ai_phrase_pipeline_with_own_session(
    input_code: str,
    normalized_code: str,
    title: str,
    components: list[CodeComponent],
) -> None:
    """Background-safe AI phrase pipeline.

    Runs LLM generation, persists cache + normalized result, and pushes the
    AI synonym + description to OCL. Opens its own SQLAlchemy session because
    the request-scoped session from ``Depends(get_db_session)`` is already
    closed when this runs (after the response has been sent).

    Errors are logged and swallowed — background tasks have no caller to
    surface them to. If Sentry/GlitchTip is wired up later, ``logger.exception``
    is captured automatically.
    """
    session = get_session_factory()()
    try:
        ai_service = AIPhraseService()
        cache_service = CacheService(session)
        normalized_results_service = NormalizedResultsService(session)
        ocl_sync_service = OCLSyncService(session)

        try:
            ai_result = ai_service.generate_ai_phrase(
                normalized_code=normalized_code,
                components=components,
                basic_title=title,
            )
        except Exception:
            logger.exception(
                "Background AI phrase generation failed",
                extra={
                    "input_code": input_code,
                    "normalized_code": normalized_code,
                },
            )
            return

        if not ai_result:
            logger.info(
                "Background AI phrase generation produced no result",
                extra={
                    "input_code": input_code,
                    "normalized_code": normalized_code,
                },
            )
            return

        try:
            cache_service.store_cached_result(
                input_code=input_code,
                normalized_code=normalized_code,
                include_ai_phrase=True,
                title=title,
                ai_phrase=ai_result.text,
                model_name=ai_result.requested_model_name,
                prompt_version=ai_service.prompt_version,
                resolved_model_name=ai_result.resolved_model_name,
            )
            normalized_results_service.upsert_result(
                normalized_code=normalized_code,
                title=title,
                ai_phrase=ai_result.text,
            )
            session.commit()
        except Exception:
            session.rollback()
            logger.exception(
                "Background AI phrase persistence failed",
                extra={
                    "input_code": input_code,
                    "normalized_code": normalized_code,
                },
            )
            return

        try:
            ocl_sync_service.sync_ai_enrichment(
                normalized_code=normalized_code,
                title=title,
                ai_phrase=ai_result.text,
                ai_model_name=ai_result.resolved_model_name,
            )
        except Exception:
            logger.exception(
                "Background OCL AI enrichment failed",
                extra={
                    "input_code": input_code,
                    "normalized_code": normalized_code,
                },
            )
    finally:
        session.close()


@router.post(
    "/normalize",
    response_model=NormalizeResponse,
    dependencies=[Depends(require_bearer_token)],
)
def normalize_codes(
    payload: NormalizeRequest,
    background_tasks: BackgroundTasks,
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

            # Either flag triggers AI work; the difference is whether we
            # block the response on it (include_ai_phrase) or fire-and-forget
            # in a background task (run_ai_phrase).
            wants_ai_phrase = (
                payload.include_ai_phrase or payload.run_ai_phrase
            ) and ai_service.should_generate_for_code(
                normalization_result.normalized_code
            )

            cached = None
            if wants_ai_phrase:
                cached = cache_service.get_cached_result(
                    normalized_code=normalization_result.normalized_code,
                    title=title,
                    include_ai_phrase=True,
                    model_name=ai_service.model_name,
                    prompt_version=ai_service.prompt_version,
                )

            if cached and cached.ai_phrase:
                # Cache hit: no LLM latency → do the full sync inline in 1 round-trip.
                ai_phrase = cached.ai_phrase
                ai_model_name = cached.resolved_model_name or cached.model_name
                from_cache = payload.include_ai_phrase

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
            else:
                # Cache miss: publish the OCL skeleton immediately so external
                # consumers polling OCL find the concept while AI enrichment
                # is still in flight (either inline or in background).
                ocl_sync_service.sync_concept_skeleton(
                    normalized_code=normalization_result.normalized_code,
                    title=title,
                    components=normalization_result.components,
                )

                if payload.include_ai_phrase and wants_ai_phrase:
                    # Synchronous path: block the response on the LLM so the
                    # caller gets ai_phrase populated.
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

                if ai_phrase:
                    ocl_sync_service.sync_ai_enrichment(
                        normalized_code=normalization_result.normalized_code,
                        title=title,
                        ai_phrase=ai_phrase,
                        ai_model_name=ai_model_name,
                    )
                elif (
                    not payload.include_ai_phrase
                    and payload.run_ai_phrase
                    and wants_ai_phrase
                ):
                    # Background path: response returns now; LLM + cache +
                    # OCL enrichment run after the response is sent.
                    # Duplicate dispatches for the same code are accepted —
                    # the cache only protects after store_cached_result.
                    background_tasks.add_task(
                        _run_ai_phrase_pipeline_with_own_session,
                        input_code=input_code,
                        normalized_code=normalization_result.normalized_code,
                        title=title,
                        components=normalization_result.components,
                    )

            # include_ai_phrase controls visibility in the response. When the
            # caller only asked for run_ai_phrase, the work may have happened
            # (cache hit + inline sync) but we keep the contract: ai_phrase
            # only appears in the response when explicitly requested.
            response_ai_phrase = ai_phrase if payload.include_ai_phrase else None

            results.append(
                NormalizeResultItem(
                    input_code=input_code,
                    normalized_code=normalization_result.normalized_code,
                    title=title,
                    ai_phrase=response_ai_phrase,
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
