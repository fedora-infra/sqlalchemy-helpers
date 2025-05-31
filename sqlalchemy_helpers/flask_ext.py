# SPDX-FileCopyrightText: 2023 Contributors to the Fedora Project
#
# SPDX-License-Identifier: LGPL-3.0-or-later

"""
Flask integration of database management.
"""

import os
from typing import Any, Callable, cast, TypeVar

import click
from flask import abort, current_app, Flask, has_app_context
from flask.cli import AppGroup
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.sql.expression import Select
from werkzeug.utils import find_modules, import_string

from .manager import DatabaseManager, SyncResult


def _get_manager(
    engine_args: dict[str, Any] | None = None, app: Flask | None = None
) -> DatabaseManager:
    """Get the database manager using the Flask app's configuration."""
    app = app or current_app
    uri = app.config["SQLALCHEMY_DATABASE_URI"]
    alembic_location = app.config["DB_ALEMBIC_LOCATION"]
    base_model = app.extensions[DatabaseExtension._app_base_model_name]
    manager = DatabaseManager(uri, alembic_location, engine_args=engine_args, base_model=base_model)
    return manager


def _syncdb() -> None:
    """Run :meth:`DatabaseManager.sync` on the command-line."""
    manager = _get_manager()
    result = manager.sync()
    if result == SyncResult.CREATED:
        click.echo("Database created.")
    elif result == SyncResult.UPGRADED:
        click.echo("Database upgraded.")
    elif result == SyncResult.ALREADY_UP_TO_DATE:
        click.echo("Database already up-to-date.")
    else:
        click.echo(f"Unexpected sync result: {result}", err=True)


# Ref: https://flask.palletsprojects.com/en/2.0.x/extensiondev/
class DatabaseExtension:
    """A Flask extension to configure the database manager according the the app's configuration.

    It cleans up database connections at the end of the requests, and creates the CLI endpoint to
    sync the database schema.
    """

    _app_manager_name = "_sqlah_database_manager"
    _app_base_model_name = "_sqlah_base_model"

    def __init__(self, app: Flask | None = None, base_model: DeclarativeBase | None = None):
        self.app = app
        self._base_model = base_model
        if app is not None:
            self.init_app(app, base_model=self._base_model)

    def init_app(self, app: Flask, base_model: DeclarativeBase | None = None) -> None:
        """Initialize the extention on the provided Flask app

        Args:
            app (flask.Flask): the Flask application.
        """
        base_model = base_model or self._base_model
        # Set config defaults
        app.config.setdefault("SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:")
        app.config.setdefault("DB_ALEMBIC_LOCATION", os.path.join(app.root_path, "migrations"))
        main_module = app.import_name
        if main_module.endswith(".app"):
            main_module = main_module[:-4]
        app.config.setdefault("DB_MODELS_LOCATION", f"{main_module}.models")
        # Connect hook
        app.before_request(self.before_request)
        # Disconnect hook
        app.teardown_appcontext(self.teardown)
        # Store the base_model
        app.extensions[self._app_base_model_name] = base_model

        # CLI
        db_cli = AppGroup("db", help="Database operations.")
        db_cli.command("sync", help="Create or migrate the database.")(_syncdb)
        app.cli.add_command(db_cli)
        # Import all modules here that might define models so that
        # they will be registered properly on the metadata.
        models_location = app.config["DB_MODELS_LOCATION"]
        try:
            for module in find_modules(models_location, include_packages=True, recursive=True):
                import_string(module)
        except ValueError:
            # It's just a module, importing it is enough
            import_string(models_location)

    def teardown(self, exception: BaseException | None) -> None:
        """Close the database connection at the end of each requests."""
        if self._app_manager_name in current_app.extensions:
            current_app.extensions[self._app_manager_name].Session.remove()

    def before_request(self) -> None:
        """Prepare the database manager at the start of each request.

        This is necessary to allow access to the ``Model.get_*`` methods.
        """
        # Just create the manager
        self.manager  # noqa: B018

    @property
    def session(self) -> Session:
        """sqlalchemy.session.Session: the database Session instance to use."""
        return self.manager.Session()

    @property
    def manager(self) -> DatabaseManager:
        """DatabaseManager: the instance of the database manager."""
        if self._app_manager_name not in current_app.extensions:
            current_app.extensions[self._app_manager_name] = _get_manager()

        return cast(DatabaseManager, current_app.extensions[self._app_manager_name])


# View helpers

M = TypeVar("M")


def get_or_404(Model: type[M], pk: Any, description: str | None = None) -> M:
    """Like ``query.get`` but aborts with 404 if not found.

    Args:
        Model: a model class.
        pk: the primary key of the desired record.
        description: a message for the 404 error if not found.
    """
    rv: M | None = Model.get_by_pk(pk)  # type: ignore
    if rv is None:
        abort(404, description=description)
    return rv


def first_or_404(
    query: Select[tuple[M]], description: str | None = None, session: Session | None = None
) -> M:
    """Like ``session.scalars(query).first()`` but aborts with 404 if not found.

    Args:
        query: a query to retrieve.
        description: a message for the 404 error if no records are found.
        session: the database session, or ``None`` to use the default session.
    """
    if not session:
        manager: DatabaseManager = current_app.extensions[DatabaseExtension._app_manager_name]
        session = manager.Session()
    rv = session.scalars(query).first()
    if rv is None:
        abort(404, description=description)
    return rv


# Useful in alembic's env.py


def get_url_from_app(app_factory: Callable[..., Flask]) -> str:
    """Get the DB URI from the app configuration

    Create the application if it hasn't been created yet. This is useful in Alembic's ``env.py``.

    Args: app_factory: the Flask application factory, to be called if this function is
        called outside of and application context.
    """
    if not has_app_context():
        app = app_factory()
        return cast(str, app.config["SQLALCHEMY_DATABASE_URI"])
    else:
        return cast(str, current_app.config["SQLALCHEMY_DATABASE_URI"])
