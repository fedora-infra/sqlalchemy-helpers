"""SQLAlchemy Helpers

A set of tools to integrate SQLAlchemy and Alembic in your project, with sane defauts.

Attributes:
    __version__ (str): this package's version.
"""

from .manager import (
    Base,
    DatabaseManager,
    DatabaseStatus,
    exists_in_db,
    get_base,
    get_or_create,
    is_sqlite,
    SyncResult,
)


# Set the version
try:
    import importlib.metadata

    __version__ = importlib.metadata.version("sqlalchemy_helpers")
except ImportError:
    try:
        import pkg_resources

        try:
            __version__ = pkg_resources.get_distribution("sqlalchemy_helpers").version
        except pkg_resources.DistributionNotFound:
            __version__ = None
    except ImportError:
        __version__ = None
