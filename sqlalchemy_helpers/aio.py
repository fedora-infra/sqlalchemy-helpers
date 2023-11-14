"""
Database management (async).

This must remain independent from any web framework.

Attributes:
    Base (object): SQLAlchemy's base class for models.
"""

import logging
from functools import wraps
from typing import Union

from alembic import command
from alembic.migration import MigrationContext
from sqlalchemy import exc as sa_exc
from sqlalchemy import select
from sqlalchemy.engine import make_url, URL
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound

from .manager import Base, DatabaseManager, model_property, SyncResult


_log = logging.getLogger(__name__)


def _async_from_sync_url(url: Union[URL, str]) -> URL:
    """Create an async DB URL from a conventional one."""
    sync_url = make_url(url)

    try:
        dialect, _ = sync_url.drivername.split("+", 1)
    except ValueError:
        dialect = sync_url.drivername

    if dialect == "sqlite":
        driver = "aiosqlite"
    elif dialect == "postgresql":
        driver = "asyncpg"
    elif dialect == "mysql":
        driver = "aiomysql"
    else:
        raise ValueError(f"I don't know the asyncio driver for dialect {dialect}")

    return sync_url.set(drivername=f"{dialect}+{driver}")


class AsyncDatabaseManager(DatabaseManager):
    """Helper for a SQLAlchemy and Alembic-powered database, asynchronous version.

    Args:
        uri (str): the database URI
        alembic_location (str): a path to the alembic directory
        engine_args (dict): additional arguments passed to ``create_async_engine``

    Attributes:
        alembic_cfg (alembic.config.Config): the Alembic configuration object
        engine (sqlalchemy.engine.Engine): the SQLAlchemy Engine instance
        Session (sqlalchemy.orm.scoped_session): the SQLAlchemy scoped session factory
    """

    def __init__(self, uri, alembic_location, engine_args=None, base_model=None):
        super().__init__(uri, alembic_location, engine_args=engine_args)
        self.Session = sessionmaker(
            class_=AsyncSession, expire_on_commit=False, bind=self.engine, future=True
        )
        self._base_model = base_model or Base
        self._base_model.get_by_pk = model_property(get_by_pk)
        self._base_model.get_one = model_property(get_one)
        self._base_model.get_or_create = model_property(get_or_create)

    def _make_engine(self, uri, engine_args):
        """Create the SQLAlchemy engine.

        Args:
            uri (str): the database URI
            engine_args (dict or None): additional arguments passed to ``create_async_engine``

        Returns:
            sqlalchemy.ext.asyncio.AsyncEngine: the SQLAlchemy engine
        """
        engine_args = engine_args or {}
        engine_args["url"] = _async_from_sync_url(uri)
        return create_async_engine(**engine_args)

    def configured_connection(self, f):
        @wraps(f)
        def wrapper(sync_connection):
            self.alembic_cfg.attributes["connection"] = sync_connection
            try:
                return f(sync_connection)
            finally:
                del self.alembic_cfg.attributes["connection"]

        return wrapper

    async def get_current_revision(self, session):
        """Get the current alembic database revision."""
        alembic_context = MigrationContext.configure(
            url=self.alembic_cfg.get_main_option("sqlalchemy.url")
        )
        try:
            result = await session.execute(alembic_context._version.select())
        except sa_exc.DatabaseError:
            # Table alembic_version does not exist yet
            return None
        current_versions = [row[0] for row in result]
        if len(current_versions) != 1:
            # Database is not setup
            return None
        return current_versions[0]

    async def create(self):
        """Create the database tables."""

        @self.configured_connection
        def _run_stamp(connection):
            self._base_model.metadata.create_all(connection)
            command.stamp(self.alembic_cfg, "head")

        async with self.engine.begin() as conn:
            await conn.run_sync(_run_stamp)

    async def upgrade(self, target="head"):
        """Upgrade the database schema."""

        @self.configured_connection
        def _run_upgrade(_conn):
            command.upgrade(self.alembic_cfg, target)

        async with self.engine.begin() as conn:
            await conn.run_sync(_run_upgrade)

    async def drop(self):
        """Drop all the database tables."""

        @self.configured_connection
        def _run_drop(connection):
            self._base_model.metadata.drop_all(connection)
            # Also drop the Alembic version table
            alembic_context = MigrationContext.configure(connection)
            alembic_context._version.drop(bind=connection)

        async with self.engine.begin() as conn:
            await conn.run_sync(_run_drop)

    async def get_status(self):
        """Get the status of the database.

        Returns:
            DatabaseStatus member: see :class:`DatabaseStatus`."""
        async with self.Session() as session:
            current = await self.get_current_revision(session=session)
        return self._compare_to_latest(current)

    async def sync(self):
        """Create or update the database schema.

        Returns:
            SyncResult member: see :class:`SyncResult`.
        """
        async with self.Session() as session:
            current_rev = await self.get_current_revision(session)
        # If the database is empty, it should be created ; otherwise it should
        # be upgraded.
        if current_rev is None:
            await self.create()
            return SyncResult.CREATED
        elif current_rev == self.get_latest_revision():
            return SyncResult.ALREADY_UP_TO_DATE
        else:
            await self.upgrade()
            return SyncResult.UPGRADED


# Query helpers


async def get_by_pk(pk, *, session, model):
    """Get a model instance using its primary key.

    Example: ``user = get_by_pk(42, session=session, model=User)``
    """
    return await session.get(model, pk)


async def get_one(session: AsyncSession, model, **attrs) -> "Base":
    """Get an object from the datbase.

    :param session: The SQLAlchemy session to use
    :param model: The SQLAlchemy model to query
    :return: the object
    """
    return (await session.execute(select(model).filter_by(**attrs))).scalar_one()


async def get_or_create(session, model, **attrs):
    """Function like Django's ``get_or_create()`` method.

    It will return a tuple, the first argument being the instance and the
    second being a boolean: ``True`` if the instance has been created and
    ``False`` otherwise.

    Example: ``user, created = get_or_create(session, User, name="foo")``
    """
    try:
        obj = await get_one(session=session, model=model, **attrs)
    except NoResultFound:
        obj = model(**attrs)
        session.add(obj)
        await session.flush()  # get an id
        created = True
    else:
        created = False

    return obj, created
