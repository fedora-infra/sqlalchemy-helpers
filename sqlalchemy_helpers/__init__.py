# SPDX-FileCopyrightText: 2023 Contributors to the Fedora Project
#
# SPDX-License-Identifier: LGPL-3.0-or-later

"""SQLAlchemy Helpers

A set of tools to integrate SQLAlchemy and Alembic in your project, with sane defauts.

Attributes:
    __version__ (str): this package's version.
"""

import importlib.metadata

from .manager import (
    Base,
    DatabaseManager,
    DatabaseStatus,
    exists_in_db,
    get_base,
    get_or_create,
    is_sqlite,
    SyncResult,
    update_or_create,
)


# Set the version
__version__ = importlib.metadata.version("sqlalchemy_helpers")
