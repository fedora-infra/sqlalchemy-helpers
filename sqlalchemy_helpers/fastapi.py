# SPDX-FileCopyrightText: 2023 Contributors to the Fedora Project
#
# SPDX-License-Identifier: LGPL-3.0-or-later

"""
FastAPI integration of database management.
"""

from collections.abc import AsyncGenerator
from typing import Any

import click
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from .aio import AsyncDatabaseManager
from .manager import SyncResult


def manager_from_config(
    db_settings: dict[str, Any] | BaseModel, *args: Any, **kwargs: Any
) -> AsyncDatabaseManager:
    """Get the database manager using the FastAPI app's configuration."""
    if not isinstance(db_settings, dict):
        db_settings = db_settings.model_dump()
    uri = str(db_settings["sqlalchemy"]["url"])
    alembic_location = str(db_settings["alembic"]["migrations_path"])
    manager = AsyncDatabaseManager(
        uri, alembic_location, *args, engine_args=db_settings["sqlalchemy"], **kwargs
    )
    return manager


async def syncdb(db_settings: dict[str, Any] | BaseModel) -> None:
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


async def make_db_session(manager: AsyncDatabaseManager) -> AsyncGenerator[AsyncSession]:
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
