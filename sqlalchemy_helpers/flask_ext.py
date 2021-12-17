"""
Flask integration of database management.
"""

import os

import click
from flask import _app_ctx_stack, abort, current_app, has_app_context
from flask.cli import AppGroup
from werkzeug.utils import find_modules, import_string

from .manager import DatabaseManager, SyncResult


def _get_manager():
    """Get the database manager using the Flask app's configuration."""
    uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
    alembic_location = current_app.config["DB_ALEMBIC_LOCATION"]
    manager = DatabaseManager(uri, alembic_location)
    return manager


def _syncdb():
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

    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """Initialize the extention on the provided Flask app

        Args:
            app (flask.Flask): the Flask application.
        """
        # Set config defaults
        app.config.setdefault("SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:")
        app.config.setdefault(
            "DB_ALEMBIC_LOCATION", os.path.join(app.root_path, "migrations")
        )
        main_module = app.import_name
        if main_module.endswith(".app"):
            main_module = main_module[:-4]
        app.config.setdefault("DB_MODELS_LOCATION", f"{main_module}.models")
        # Connect hook
        app.before_request(self.before_request)
        # Disconnect hook
        app.teardown_appcontext(self.teardown)
        # CLI
        db_cli = AppGroup("db", help="Database operations.")
        db_cli.command("sync", help="Create or migrate the database.")(_syncdb)
        app.cli.add_command(db_cli)
        # Import all modules here that might define models so that
        # they will be registered properly on the metadata.
        models_location = app.config["DB_MODELS_LOCATION"]
        try:
            for module in find_modules(
                models_location, include_packages=True, recursive=True
            ):
                import_string(module)
        except ValueError:
            # It's just a module, importing it is enough
            import_string(models_location)

    def teardown(self, exception):
        """Close the database connection at the end of each requests."""
        ctx = _app_ctx_stack.top
        if hasattr(ctx, "database_manager"):
            ctx.database_manager.Session.remove()

    def before_request(self):
        """Prepare the database manager at the start of each request.

        This is necessary to allow access to the ``Model.query`` property.
        """
        # Just create the manager
        self.manager

    @property
    def session(self):
        """sqlalchemy.session.Session: the database Session instance to use."""
        return self.manager.Session()

    @property
    def manager(self):
        """DatabaseManager: the instance of the database manager."""
        ctx = _app_ctx_stack.top
        if ctx is not None:
            if not hasattr(ctx, "database_manager"):
                ctx.database_manager = _get_manager()
            return ctx.database_manager


# View helpers


def get_or_404(Model, ident, description=None):
    """Like ``query.get`` but aborts with 404 if not found.

    Args:
        Model (manager.Base): a model class.
        ident (int or str): the primary key of the desired record.
        description (str, optional): a message for the 404 error if not found.
    """
    rv = Model.query.get(ident)
    if rv is None:
        abort(404, description=description)
    return rv


def first_or_404(query, description=None):
    """Like ``query.first`` but aborts with 404 if not found.

    Args:
        query (sqlalchemy.orm.Query): a query to retrieve.
        description (str, optional): a message for the 404 error if no records are found.
    """
    rv = query.first()
    if rv is None:
        abort(404, description=description)
    return rv


# Useful in alembic's env.py


def get_url_from_app(app_factory):
    """Get the DB URI from the app configuration

    Create the application if it hasn't been created yet. This is useful in Alembic's ``env.py``.

    Args: app_factory (callable): the Flask application factory, to be called if this function is
        called outside of and application context.
    """
    if not has_app_context():
        app = app_factory()
        return app.config["SQLALCHEMY_DATABASE_URI"]
    else:
        return current_app.config["SQLALCHEMY_DATABASE_URI"]
