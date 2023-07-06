"""
FastAPI integration of database management.
"""

from typing import Iterator

import click
from sqlalchemy.ext.asyncio import AsyncSession

from .aio import AsyncDatabaseManager
from .manager import SyncResult


def manager_from_config(db_settings):
    """Get the database manager using the Flask app's configuration."""
    if not isinstance(db_settings, dict):
        try:
            db_settings = db_settings.model_dump()  # Pydantic Settings >=2.0
        except AttributeError:  # pragma: no cover
            db_settings = db_settings.dict()  # Pydantic <2.0
    uri = str(db_settings["sqlalchemy"]["url"])
    alembic_location = str(db_settings["alembic"]["migrations_path"])
    manager = AsyncDatabaseManager(
        uri, alembic_location, engine_args=db_settings["sqlalchemy"]
    )
    return manager


async def syncdb(db_settings):
    """Run :meth:`DatabaseManager.sync` on the command-line."""
    manager = manager_from_config(db_settings)
    result = await manager.sync()
    if result == SyncResult.CREATED:
        click.echo("Database created.")
    elif result == SyncResult.UPGRADED:
        click.echo("Database upgraded.")
    elif result == SyncResult.ALREADY_UP_TO_DATE:
        click.echo("Database already up-to-date.")
    else:
        click.echo(f"Unexpected sync result: {result}", err=True)


async def make_db_session(manager) -> Iterator[AsyncSession]:
    """Generate database sessions for FastAPI request handlers.

    This lets users declare the session as a dependency in request handler
    functions, e.g.::

        @app.get("/path")
        def process_path(db_session: AsyncSession = Depends(make_db_session)):
            query = select(Model).filter_by(...)
            result = await db_session.execute(query)
            ...

    :return: A :class:`sqlalchemy.ext.asyncio.AsyncSession` object for the
        current request
    """
    session = manager.Session()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
