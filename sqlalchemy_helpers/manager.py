# SPDX-FileCopyrightText: 2023 Contributors to the Fedora Project
#
# SPDX-License-Identifier: LGPL-3.0-or-later

"""
Database management.

This must remain independent from any web framework.
"""

import enum
import logging
import os
import warnings
from abc import ABCMeta, abstractmethod
from collections.abc import Mapping, MutableMapping
from contextlib import AbstractContextManager, nullcontext
from functools import partial
from sqlite3 import Connection as SQLite3Connection
from typing import Any, Callable, cast, TYPE_CHECKING, TypeVar

from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, create_engine, MetaData, select
from sqlalchemy import event as sa_event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import DeclarativeBase, scoped_session, Session, sessionmaker


try:
    from typing import Self
except ImportError:  # pragma: no cover
    # Python < 3.11
    Self = TypeVar("Self", bound="Base")  # type: ignore


_log = logging.getLogger(__name__)

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """SQLAlchemy's base class for models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    if TYPE_CHECKING:
        # These methods will be added by the Manager
        @classmethod
        def get_by_pk(cls, pk: Any) -> Self | None: ...
        @classmethod
        def get_one(cls, **attrs: Any) -> Self: ...
        @classmethod
        def get_or_create(cls, **attrs: Any) -> tuple[Self, bool]: ...
        @classmethod
        def update_or_create(
            cls,
            defaults: Mapping[str, Any] | None = None,
            create_defaults: Mapping[str, Any] | None = None,
            **filter_attrs: Any,
        ) -> tuple[Self, bool]: ...


def get_base(*args: Any, **kwargs: Any) -> type[DeclarativeBase]:
    warnings.warn(
        "get_base() is deprecated, please use the Base class and subclass it if necessary",
        DeprecationWarning,
        stacklevel=2,
    )
    return Base


class BaseDatabaseManager(metaclass=ABCMeta):
    """Helper for a SQLAlchemy and Alembic-powered database

    Args:
        uri: the database URI
        alembic_location: a path to the alembic directory
        engine_args: additional arguments passed to ``create_engine``

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
        self.engine = self._make_engine(uri, engine_args)
        self._base_model = base_model or Base
        # Alembic
        self.alembic_cfg = AlembicConfig(os.path.join(alembic_location, "alembic.ini"))
        self.alembic_cfg.set_main_option("script_location", alembic_location)
        self.alembic_cfg.set_main_option("sqlalchemy.url", uri.replace("%", "%%"))

    @abstractmethod
    def _make_engine(self, uri: str, engine_args: MutableMapping[str, Any] | None) -> Any: ...

    def get_latest_revision(self) -> str | None:
        """Get the most up-to-date alembic database revision available."""
        script_dir = ScriptDirectory.from_config(self.alembic_cfg)
        return script_dir.get_current_head()

    def _compare_to_latest(self, current: str | None) -> "DatabaseStatus":
        if current is None:
            return DatabaseStatus.NO_INFO
        latest = self.get_latest_revision()
        if current != latest:
            return DatabaseStatus.UPGRADE_AVAILABLE
        return DatabaseStatus.UP_TO_DATE


class DatabaseManager(BaseDatabaseManager):
    """Helper for a SQLAlchemy and Alembic-powered database

    Args:
        uri: the database URI
        alembic_location: a path to the alembic directory
        engine_args: additional arguments passed to ``create_engine``

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
        self.engine = cast(Engine, self.engine)
        self.Session = scoped_session(
            sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        )
        self._base_model.get_by_pk = session_and_model_property(self.Session, get_by_pk)
        self._base_model.get_one = session_and_model_property(self.Session, get_one)
        self._base_model.get_or_create = session_and_model_property(self.Session, get_or_create)
        self._base_model.update_or_create = session_and_model_property(
            self.Session, update_or_create
        )

    def _make_engine(self, uri: str, engine_args: MutableMapping[str, Any] | None) -> Engine:
        """Create the SQLAlchemy engine.

        Args:
            uri: the database URI
            engine_args: additional arguments passed to ``create_engine``

        Returns:
            the SQLAlchemy engine
        """
        engine_args = engine_args or {}
        engine_args["url"] = uri
        return create_engine(**engine_args)

    def _get_session_context(
        self, session: Session | None = None
    ) -> AbstractContextManager[Session]:
        if session is None:
            return self.Session()
        else:
            return nullcontext(session)

    def get_current_revision(self, session: Session | None = None) -> str | None:
        """Get the current alembic database revision.

        Args:
            session: the session instance to use, or ``None``
                if one is to be created.
        """
        with self._get_session_context(session) as session:
            alembic_context = MigrationContext.configure(session.connection())
            return alembic_context.get_current_revision()

    def create(self) -> None:
        """Create the database tables."""
        self._base_model.metadata.create_all(bind=self.engine)
        command.stamp(self.alembic_cfg, "head")

    def upgrade(self, target: str = "head") -> None:
        """Upgrade the database schema."""
        command.upgrade(self.alembic_cfg, target)

    def drop(self) -> None:
        """Drop all the database tables."""
        self._base_model.metadata.drop_all(bind=self.engine)
        # Also drop the Alembic version table
        with self.engine.connect() as connection:
            with connection.begin():
                alembic_context = MigrationContext.configure(connection)
                alembic_context._version.drop(bind=connection)

    def get_status(self, session: Session | None = None) -> "DatabaseStatus":
        """Get the status of the database.

        Args:
            session: the session instance to use, or ``None``
                if one is to be created.

        Returns:
            the database status, see :class:`DatabaseStatus`.
        """
        with self._get_session_context(session) as session:
            current = self.get_current_revision(session=session)
        return self._compare_to_latest(current)

    def sync(self, session: Session | None = None) -> "SyncResult":
        """Create or update the database schema.

        Args:
            session: the session instance to use, or ``None``
                if one is to be created.

        Returns:
            the result of the sync, see :class:`SyncResult`.
        """
        with self._get_session_context(session) as session:
            current_rev = self.get_current_revision(session)
        # If the database is empty, it should be created ; otherwise it should
        # be upgraded.
        if current_rev is None:
            self.create()
            return SyncResult.CREATED
        elif current_rev == self.get_latest_revision():
            return SyncResult.ALREADY_UP_TO_DATE
        else:
            self.upgrade()
            return SyncResult.UPGRADED


class DatabaseStatus(enum.Enum):
    """The status of the database."""

    UP_TO_DATE = enum.auto()
    """Returned when the database schema is up-to-date."""
    NO_INFO = enum.auto()
    """Returned when the database couldn't be connected to."""
    UPGRADE_AVAILABLE = enum.auto()
    """Returned when the database schema can be upgraded."""


class SyncResult(enum.Enum):
    """The result of a sync() call."""

    ALREADY_UP_TO_DATE = enum.auto()
    """Returned when the database schema was already up-to-date."""
    CREATED = enum.auto()
    """Returned when the database has been created."""
    UPGRADED = enum.auto()
    """Returned when the database schema has been upgraded."""


# Events


@sa_event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
    """Automatically activate foreign keys on SQLite databases."""
    if isinstance(dbapi_connection, SQLite3Connection):  # pragma: no cover
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# Query helpers

M = TypeVar("M")


def get_by_pk(pk: Any, *, session: Session, model: type[M]) -> M | None:
    """Get a model instance using its primary key.

    Example: ``user = get_by_pk(42, session=session, model=User)``
    """
    return session.get(model, pk)


def get_one(session: Session, model: type[M], **attrs: Any) -> M:
    """Get a model instance using filters.

    Example: ``user = get_one(session, User, name="foo")``
    """
    return session.scalars(select(model).filter_by(**attrs)).one()


def get_or_create(session: Session, model: type[M], **attrs: Any) -> tuple[M, bool]:
    """Function like Django's ``get_or_create()`` method.

    It will return a tuple, the first argument being the instance and the
    second being a boolean: ``True`` if the instance has been created and
    ``False`` otherwise.

    Example: ``user, created = get_or_create(session, User, name="foo")``
    """
    try:
        return get_one(session=session, model=model, **attrs), False
    except NoResultFound:
        obj = model(**attrs)
        session.add(obj)
        session.flush()  # get an id
        return obj, True


def update_or_create(
    session: Session,
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
        obj = get_one(session=session, model=model, **filter_attrs)
        for key, value in defaults.items():
            setattr(obj, key, value)
        return obj, False
    except NoResultFound:
        new_attrs = filter_attrs.copy()
        new_attrs.update(create_defaults)
        obj = model(**new_attrs)
        session.add(obj)
        session.flush()  # get an id
        return obj, True


def session_and_model_property(Session: scoped_session[Session], func: Callable[..., Any]) -> Any:
    """Add a model property that uses the database session."""

    # https://docs.python.org/3/howto/descriptor.html
    class accessor:
        def __get__(self, obj: Any, objtype: type[DeclarativeBase] | None = None) -> Any:
            return partial(func, session=Session(), model=objtype)

    return accessor()


def model_property(func: Callable[..., Any]) -> Any:
    """Add a model property to call a function that uses the database model."""

    # https://docs.python.org/3/howto/descriptor.html
    class accessor:
        def __get__(self, obj: Any, objtype: type[DeclarativeBase] | None = None) -> Any:
            return partial(func, model=objtype)

    return accessor()


# Migration helpers


def is_sqlite(bind: Engine | Connection) -> bool:
    """Check whether the database is SQLite.

    Returns:
        bool: whether the database is SQLite."""
    return bind.dialect.name == "sqlite"


def exists_in_db(bind: Engine | Connection, tablename: str, columnname: str | None = None) -> bool:
    """Check whether a table and optionally a column exist in the database.

    Args:
        bind: the database engine or connection.
        tablename: the table to look for.
        columnname: the column to look for, if any. Defaults to None.

    Returns:
        Whether the database (and column) exist.
    """
    md = MetaData()
    md.reflect(bind=bind)
    if columnname is None:
        return tablename in md.tables
    else:
        return tablename in md.tables and columnname in [
            c.name for c in md.tables[tablename].columns
        ]
