import logging

from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.init_db import init_db
from app.db.models import SimpleTabulationCode
from app.db.session import get_session_factory
from app.services.importer import SimpleTabulationImporter


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger(__name__)


def main() -> int:
    settings = get_settings()
    init_db()

    session = get_session_factory()()
    try:
        reference_rows = session.scalar(
            select(func.count()).select_from(SimpleTabulationCode)
        ) or 0
        if reference_rows > 0:
            logger.info(
                "Skipping Simple Tabulation bootstrap because %s reference rows already exist",
                reference_rows,
            )
            return 0

        logger.info(
            "Simple Tabulation table is empty. Importing WHO dataset from %s",
            settings.simple_tabulation_zip_url,
        )
        summary = SimpleTabulationImporter(session).import_from_url(
            zip_url=settings.simple_tabulation_zip_url,
            replace=True,
        )
        logger.info(
            "Bootstrap import completed with %s inserted rows",
            summary.inserted_rows,
        )
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
