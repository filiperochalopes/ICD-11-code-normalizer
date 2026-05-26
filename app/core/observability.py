"""Sentry/GlitchTip wiring for the code-normalizer service.

The same sentry-sdk client works against GlitchTip — point ``SENTRY_DSN`` at
the GlitchTip project DSN and the rest behaves identically.
"""
from __future__ import annotations

import logging

from app.core.config import get_settings


logger = logging.getLogger(__name__)


def init_sentry() -> bool:
    """Initialize sentry-sdk if a DSN is configured.

    Returns:
    - True when the SDK was initialized, False when skipped (no DSN configured
      or sentry-sdk is not installed).
    """
    settings = get_settings()
    dsn = settings.sentry_dsn.strip()
    if not dsn:
        logger.info("Sentry/GlitchTip not configured (SENTRY_DSN empty); skipping init")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError:
        logger.warning(
            "sentry-sdk is not installed; skipping init even though SENTRY_DSN is set"
        )
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=settings.sentry_environment or settings.app_env,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        integrations=[
            StarletteIntegration(),
            FastApiIntegration(),
        ],
        # logger.exception(...) is captured automatically via the default
        # LoggingIntegration; extra kwargs flow through as event tags/extras.
    )
    logger.info(
        "Sentry initialized (environment=%s, traces_sample_rate=%s)",
        settings.sentry_environment or settings.app_env,
        settings.sentry_traces_sample_rate,
    )
    return True
