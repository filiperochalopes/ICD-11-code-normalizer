import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.api.routes import router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.init_db import init_db


configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    init_db()
    logger.info("Application startup complete")
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def log_request_timing(request: Request, call_next):
    started_at = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    logger.info(
        "%s %s completed in %.2fms",
        request.method,
        request.url.path,
        elapsed_ms,
    )
    return response


app.include_router(router)

