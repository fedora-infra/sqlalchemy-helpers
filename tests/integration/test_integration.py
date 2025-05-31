# SPDX-FileCopyrightText: 2023 Contributors to the Fedora Project
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import os
import subprocess
import sys
from importlib import import_module

import alembic


def test_config(full_app: None, clear_metadata: None, tmpdir: str) -> None:
    """Check that the app configuration is set."""
    app_module = import_module("testapp.app")
    config = app_module.app.config
    assert config["SQLALCHEMY_DATABASE_URI"] == f"sqlite:///{tmpdir}/database.sqlite"
    assert config["DB_ALEMBIC_LOCATION"] == os.path.join(tmpdir, "testapp", "migrations")
    assert config["DB_MODELS_LOCATION"] == "testapp.models"


def test_models(full_app: None, clear_metadata: None, tmpdir: str) -> None:
    """Check that the models were properly imported."""
    import_module("testapp.app")
    manager_module = import_module("sqlalchemy_helpers.manager")
    assert "app_users" in manager_module.Base.metadata.tables


def test_sync_db(full_app: None, tmpdir: str) -> None:
    """Check that the CLI extension works."""

    def syncdb() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "flask", "db", "sync"],
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        )

    result = syncdb()
    assert os.path.exists(os.path.join(tmpdir, "database.sqlite"))
    assert "Database created." in result.stdout
    result = syncdb()
    assert "Database already up-to-date." in result.stdout
    # Add a revision
    alembic_cfg = alembic.config.Config(
        os.path.join(tmpdir, "testapp", "migrations", "alembic.ini")
    )
    alembic.command.revision(alembic_cfg, rev_id="new")
    result = syncdb()
    assert "Database upgraded." in result.stdout
