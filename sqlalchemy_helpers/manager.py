"""
Database management.

This must remain independent from any web framework.

Attributes:
    Base (object): SQLAlchemy's base class for models.
"""

import enum
import logging
import os
from functools import partial
from sqlite3 import Connection as SQLite3Connection

from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, MetaData
from sqlalchemy import event as sa_event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker
from sqlalchemy.orm.exc import NoResultFound


def get_base(*args, **kwargs):
    """A wrapper for :func:`declarative_base`."""
    base = declarative_base(*args, **kwargs)
    base.metadata.naming_convention = {
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
    return base


Base = get_base()


_log = logging.getLogger(__name__)


class DatabaseManager:
    """Helper for a SQLAlchemy and Alembic-powered database

    Args:
        uri (str): the database URI
        alembic_location (str): a path to the alembic directory
        engine_args (dict): additional arguments passed to ``create_engine``

    Attributes:
        alembic_cfg (alembic.config.Config): the Alembic configuration object
        engine (sqlalchemy.engine.Engine): the SQLAlchemy Engine instance
        Session (sqlalchemy.orm.scoped_session): the SQLAlchemy scoped session factory
    """

    def __init__(self, uri, alembic_location, engine_args=None, base_model=None):
        self.engine = self._make_engine(uri, engine_args)
        self.Session = scoped_session(
            sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        )
        self._base_model = base_model or Base
        self._base_model.get_by_pk = session_and_model_property(self.Session, get_by_pk)
        self._base_model.get_one = session_and_model_property(self.Session, get_one)
        self._base_model.get_or_create = session_and_model_property(
            self.Session, get_or_create
        )
        # Alembic
        self.alembic_cfg = AlembicConfig(os.path.join(alembic_location, "alembic.ini"))
        self.alembic_cfg.set_main_option("script_location", alembic_location)
        self.alembic_cfg.set_main_option("sqlalchemy.url", uri.replace("%", "%%"))

    def _make_engine(self, uri, engine_args):
        """Create the SQLAlchemy engine.

        Args:
            uri (str): the database URI
            engine_args (dict or None): additional arguments passed to ``create_engine``

        Returns:
            sqlalchemy.Engine: the SQLAlchemy engine
        """
        engine_args = engine_args or {}
        engine_args["url"] = uri
        return create_engine(**engine_args)

    def get_current_revision(self, session):
        """Get the current alembic database revision."""
        alembic_context = MigrationContext.configure(session.connection())
        return alembic_context.get_current_revision()

    def get_latest_revision(self):
        """Get the most up-to-date alembic database revision available."""
        script_dir = ScriptDirectory.from_config(self.alembic_cfg)
        return script_dir.get_current_head()

    def create(self):
        """Create the database tables."""
        self._base_model.metadata.create_all(bind=self.engine)
        command.stamp(self.alembic_cfg, "head")

    def upgrade(self, target="head"):
        """Upgrade the database schema."""
        command.upgrade(self.alembic_cfg, target)

    def drop(self):
        """Drop all the database tables."""
        self._base_model.metadata.drop_all(bind=self.engine)
        # Also drop the Alembic version table
        with self.engine.connect() as connection:
            with connection.begin():
                alembic_context = MigrationContext.configure(connection)
                alembic_context._version.drop(bind=connection)

    def get_status(self):
        """Get the status of the database.

        Returns:
            DatabaseStatus member: see :class:`DatabaseStatus`."""
        with self.Session() as session:
            current = self.get_current_revision(session=session)
        return self._compare_to_latest(current)

    def _compare_to_latest(self, current):
        if current is None:
            return DatabaseStatus.NO_INFO
        latest = self.get_latest_revision()
        if current != latest:
            return DatabaseStatus.UPGRADE_AVAILABLE
        return DatabaseStatus.UP_TO_DATE

    def sync(self):
        """Create or update the database schema.

        Returns:
            SyncResult member: see :class:`SyncResult`.
        """
        with self.Session() as session:
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
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Automatically activate foreign keys on SQLite databases."""
    if isinstance(dbapi_connection, SQLite3Connection):  # pragma: no cover
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# Query helpers


def get_by_pk(pk, *, session, model):
    """Get a model instance using its primary key.

    Example: ``user = get_by_pk(42, session=session, model=User)``
    """
    return session.get(model, pk)


def get_one(session, model, **attrs):
    """Get a model instance using filters.

    Example: ``user = get_one(session, User, name="foo")``
    """
    return session.query(model).filter_by(**attrs).one()


def get_or_create(session, model, **attrs):
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


def session_and_model_property(Session, func):
    """Add a model property that uses the database session."""

    # https://docs.python.org/3/howto/descriptor.html
    class accessor:
        def __get__(self, obj, objtype=None):
            return partial(func, session=Session(), model=objtype)

    return accessor()


def model_property(func):
    """Add a model property to call a function that uses the database model."""

    # https://docs.python.org/3/howto/descriptor.html
    class accessor:
        def __get__(self, obj, objtype=None):
            return partial(func, model=objtype)

    return accessor()


# Migration helpers


def is_sqlite(bind):
    """Check whether the database is SQLite.

    Returns:
        bool: whether the database is SQLite."""
    return bind.dialect.name == "sqlite"


def exists_in_db(bind, tablename, columnname=None):
    """Check whether a table and optionally a column exist in the database.

    Args:
        bind (sqlalchemy.engine.Engine): the database engine or connection.
        tablename (str): the table to look for.
        columnname (str, optional): the column to look for, if any. Defaults to None.

    Returns:
        bool: Whether the database (and column) exist.
    """
    md = MetaData()
    md.reflect(bind=bind)
    if columnname is None:
        return tablename in md.tables
    else:
        return tablename in md.tables and columnname in [
            c.name for c in md.tables[tablename].columns
        ]
