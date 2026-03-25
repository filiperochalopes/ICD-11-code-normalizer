import json
import secrets

import typer
from sqlalchemy import func, select, text

from app.core.config import get_settings
from app.db.init_db import init_db
from app.db.models import GeneratedCache, SimpleTabulationCode
from app.db.session import get_session_factory
from app.services.importer import ImporterError, SimpleTabulationImporter


cli = typer.Typer(no_args_is_help=True, help="Operational CLI for the ICD-11 microservice.")


@cli.command("import-simple-tabulation")
def import_simple_tabulation(
    zip_url: str = typer.Option(
        default=get_settings().simple_tabulation_zip_url,
        help="Official WHO ZIP URL containing the Simple Tabulation workbook.",
    ),
    replace: bool = typer.Option(
        True,
        "--replace/--no-replace",
        help="Replace existing reference rows before importing.",
    ),
) -> None:
    init_db()
    session = get_session_factory()()
    try:
        summary = SimpleTabulationImporter(session).import_from_url(zip_url=zip_url, replace=replace)
        typer.echo(json.dumps(summary.to_dict(), indent=2))
    except ImporterError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    finally:
        session.close()


@cli.command("create-token")
def create_token(
    length: int = typer.Option(
        32,
        min=16,
        help="Number of random bytes used before URL-safe encoding.",
    ),
) -> None:
    typer.echo(secrets.token_urlsafe(length))


@cli.command("show-config")
def show_config() -> None:
    typer.echo(json.dumps(get_settings().public_summary(), indent=2))


@cli.command("healthcheck-db")
def healthcheck_db() -> None:
    init_db()
    session = get_session_factory()()
    try:
        session.execute(text("SELECT 1"))
        reference_rows = session.scalar(
            select(func.count()).select_from(SimpleTabulationCode)
        ) or 0
        cache_rows = session.scalar(select(func.count()).select_from(GeneratedCache)) or 0
        typer.echo(
            json.dumps(
                {
                    "status": "ok",
                    "database_url": get_settings().database_url,
                    "reference_rows": reference_rows,
                    "cache_rows": cache_rows,
                },
                indent=2,
            )
        )
    finally:
        session.close()


if __name__ == "__main__":
    cli()

