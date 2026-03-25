#!/usr/bin/env python3
import argparse
import json

from app.core.config import get_settings
from app.db.init_db import init_db
from app.db.session import get_session_factory
from app.services.importer import ImporterError, SimpleTabulationImporter


def parse_args() -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description="Download, extract and import the official WHO Simple Tabulation spreadsheet."
    )
    parser.add_argument(
        "--zip-url",
        default=settings.simple_tabulation_zip_url,
        help="Official WHO ZIP URL.",
    )
    parser.add_argument(
        "--no-replace",
        action="store_true",
        help="Update existing rows instead of replacing the full reference table.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    session = get_session_factory()()

    try:
        summary = SimpleTabulationImporter(session).import_from_url(
            zip_url=args.zip_url,
            replace=not args.no_replace,
        )
    except ImporterError as exc:
        print(str(exc))
        return 1
    finally:
        session.close()

    print(json.dumps(summary.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

