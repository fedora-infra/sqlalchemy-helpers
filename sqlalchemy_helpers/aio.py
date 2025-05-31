# SPDX-FileCopyrightText: 2023 Contributors to the Fedora Project
#
# SPDX-License-Identifier: LGPL-3.0-or-later

"""
Database management (async).

This must remain independent from any web framework.
"""

import logging
from collections.abc import Mapping, MutableMapping
from functools import wraps
from typing import Any, Callable, cast, TYPE_CHECKING, TypeVar, Union

from alembic import command
from alembic.migration import MigrationContext
from sqlalchemy import exc as sa_exc
from sqlalchemy import MetaData, select
from sqlalchemy.engine import Connection, make_url, URL
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    AsyncAttrs,
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .manager import (
    BaseDatabaseManager,
    DatabaseStatus,
    model_property,
    NAMING_CONVENTION,
    SyncResult,
)


try:
    from typing import Self
except ImportError:  # pragma: no cover
    # Python < 3.11
    Self = TypeVar("Self", bound="Base")  # type: ignore


_log = logging.getLogger(__name__)


class Base(AsyncAttrs, DeclarativeBase):
    """SQLAlchemy's base class for async models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    if TYPE_CHECKING:
        # These methods will be added by the Manager
        @classmethod
        async def get_by_pk(cls, session: AsyncSession, pk: Any) -> Self | None: ...
        @classmethod
        async def get_one(cls, session: AsyncSession, **attrs: Any) -> Self: ...
        @classmethod
        async def get_or_create(cls, session: AsyncSession, **attrs: Any) -> tuple[Self, bool]: ...
        @classmethod
        async def update_or_create(
            cls,
            session: AsyncSession,
            defaults: Mapping[str, Any] | None = None,
            create_defaults: Mapping[str, Any] | None = None,
            **filter_attrs: Any,
        ) -> tuple[Self, bool]: ...


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


R = TypeVar("R")


class AsyncDatabaseManager(BaseDatabaseManager):
    """Helper for a SQLAlchemy and Alembic-powered database, asynchronous version.

    Args:
        uri: the database URI
        alembic_location: a path to the alembic directory
        engine_args: additional arguments passed to ``create_async_engine``

    Attributes:
        alembic_cfg (alembic.config.Config): the Alembic configuration object
        engine (sqlalchemy.engine.Engine): the SQLAlchemy Engine instance
        Session (sqlalchemy.orm.scoped_session): the SQLAlchemy scoped session factory
    """

    def __init__(
        self,
        uri: str,
        alembic_location: str,
        *,
        engine_args: MutableMapping[str, Any] | None = None,
        base_model: type[DeclarativeBase] | None = None,
    ):
        super().__init__(uri, alembic_location, engine_args=engine_args, base_model=base_model)
        self.engine = cast(AsyncEngine, self.engine)
        self.Session = async_sessionmaker(expire_on_commit=False, bind=self.engine, future=True)
        self._base_model = base_model or Base
        self._base_model.get_by_pk = model_property(get_by_pk)
        self._base_model.get_one = model_property(get_one)
        self._base_model.get_or_create = model_property(get_or_create)
        self._base_model.update_or_create = model_property(update_or_create)

    def _make_engine(self, uri: str, engine_args: MutableMapping[str, Any] | None) -> AsyncEngine:
        """Create the SQLAlchemy engine.

        Args:
            uri: the database URI
            engine_args: additional arguments passed to ``create_async_engine``

        Returns:
            the SQLAlchemy async engine
        """
        engine_args = engine_args or {}
        engine_args["url"] = _async_from_sync_url(uri)
        return create_async_engine(**engine_args)

    def configured_connection(self, f: Callable[[Connection], R]) -> Callable[[Connection], R]:
        @wraps(f)
        def wrapper(sync_connection: Connection) -> R:
            self.alembic_cfg.attributes["connection"] = sync_connection
            try:
                return f(sync_connection)
            finally:
                del self.alembic_cfg.attributes["connection"]

        return wrapper

    async def get_current_revision(self, session: AsyncSession) -> str | None:
        """Get the current alembic database revision."""
        alembic_context = MigrationContext.configure(
            url=self.alembic_cfg.get_main_option("sqlalchemy.url")
        )
        try:
            result = await session.execute(alembic_context._version.select())
        except sa_exc.DatabaseError:
            # Table alembic_version does not exist yet
            return None
        current_versions = cast(list[str], [row[0] for row in result])
        if len(current_versions) != 1:
            # Database is not setup
            return None
        return current_versions[0]

    async def create(self) -> None:
        """Create the database tables."""

        @self.configured_connection
        def _run_stamp(connection: Connection) -> None:
            self._base_model.metadata.create_all(connection)
            command.stamp(self.alembic_cfg, "head")

        async with self.engine.begin() as conn:
            await conn.run_sync(_run_stamp)

    async def upgrade(self, target: str = "head") -> None:
        """Upgrade the database schema."""

        @self.configured_connection
        def _run_upgrade(_conn: Connection) -> None:
            command.upgrade(self.alembic_cfg, target)

        async with self.engine.begin() as conn:
            await conn.run_sync(_run_upgrade)

    async def drop(self) -> None:
        """Drop all the database tables."""

        @self.configured_connection
        def _run_drop(connection: Connection) -> None:
            self._base_model.metadata.drop_all(connection)
            # Also drop the Alembic version table
            alembic_context = MigrationContext.configure(connection)
            alembic_context._version.drop(bind=connection)

        async with self.engine.begin() as conn:
            await conn.run_sync(_run_drop)

    async def get_status(self) -> DatabaseStatus:
        """Get the status of the database.

        Returns:
            the status of the database, see :class:`DatabaseStatus`."""
        async with self.Session() as session:
            current = await self.get_current_revision(session=session)
        return self._compare_to_latest(current)

    async def sync(self) -> SyncResult:
        """Create or update the database schema.

        Returns:
            the result of the sync, see :class:`SyncResult`.
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

M = TypeVar("M")


async def get_by_pk(pk: Any, *, session: AsyncSession, model: type[M]) -> M | None:
    """Get a model instance using its primary key.

    Example:

        user = get_by_pk(42, session=session, model=User)
    """
    return await session.get(model, pk)


async def get_one(session: AsyncSession, model: type[M], **attrs: Any) -> M:
    """Get an object from the datbase.

    Args:
        session: The SQLAlchemy session to use
        model: The SQLAlchemy model to query

    Returns:
        the model instance
    """
    return (await session.execute(select(model).filter_by(**attrs))).scalar_one()


async def get_or_create(session: AsyncSession, model: type[M], **attrs: Any) -> tuple[M, bool]:
    """Function like Django's ``get_or_create()`` method.

    It will return a tuple, the first argument being the instance and the
    second being a boolean: ``True`` if the instance has been created and
    ``False`` otherwise.

    Example::

        user, created = get_or_create(session, User, name="foo")
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


async def update_or_create(
    session: AsyncSession,
    model: type[M],
    defaults: Mapping[str, Any] | None = None,
    create_defaults: Mapping[str, Any] | None = None,
    **filter_attrs: Any,
) -> tuple[M, bool]:
    """Function like Django's ``update_or_create()`` method.

    It will return a tuple, the first argument being the instance and the
    second being a boolean: ``True`` if the instance has been created and
    ``False`` otherwise.

    Example::

        user, created = update_or_create(session, User, name="foo", defaults={"full_name": "Foo"})

    """
    defaults = defaults or {}
    create_defaults = create_defaults or defaults
    try:
        obj = await get_one(session=session, model=model, **filter_attrs)
        for key, value in defaults.items():
            setattr(obj, key, value)
        return obj, False
    except NoResultFound:
        new_attrs = filter_attrs.copy()
        new_attrs.update(create_defaults)
        obj = model(**new_attrs)
        session.add(obj)
        await session.flush()  # get an id
        return obj, True
