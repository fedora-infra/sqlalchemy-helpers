# SPDX-FileCopyrightText: 2023 Contributors to the Fedora Project
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import os
import pathlib
import sys
from collections.abc import AsyncGenerator, Generator
from contextlib import suppress
from importlib import import_module
from shutil import copyfile
from typing import Any, Callable

import alembic
import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from sqlalchemy_helpers.manager import Base


ROOT = pathlib.Path(__file__).parent.parent


@pytest.fixture
def app(tmpdir: str) -> dict[str, Any]:
    db_uri = f"sqlite:///{tmpdir}/database.sqlite"
    alembic_dir = os.path.join(tmpdir, "alembic")
    alembic_cfg = alembic.config.Config(os.path.join(alembic_dir, "alembic.ini"))
    alembic.command.init(alembic_cfg, alembic_dir)

    if "users" not in Base.metadata.tables:
        # Reimport the test models, the metadata has been cleared by a previous test
        with suppress(KeyError):
            del sys.modules["tests.unit.models"]
        import_module("tests.unit.models")

    return {
        "db_uri": db_uri,
        "tmpdir": tmpdir,
        "alembic_dir": alembic_dir,
        "alembic_cfg": alembic_cfg,
    }


@pytest.fixture
def async_enabled_env_script(app: dict[str, str]) -> None:
    copyfile(
        ROOT / "docs" / "aio-env.py.example",
        pathlib.Path(app["alembic_dir"]) / "env.py",
    )


@pytest.fixture
def session(manager: Any) -> Generator[Session]:
    with manager.Session() as session:
        yield session


@pytest.fixture
async def async_session(manager: Any) -> AsyncGenerator[AsyncSession]:
    async with manager.Session() as session:
        yield session


@pytest.fixture
def flask_client(flask_app: Flask) -> Generator[FlaskClient]:
    with flask_app.test_client() as client:
        with flask_app.app_context():
            yield client


@pytest.fixture
def flask_app_factory(tmpdir: str, app: dict[str, Any]) -> Callable[..., Flask]:
    def create_app(config: dict[str, Any] | None = None) -> Flask:
        flask_app = Flask("tests")
        flask_app.config.update(
            {
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmpdir}/database.sqlite",
                "DB_MODELS_LOCATION": "tests.unit.models",
                "DB_ALEMBIC_LOCATION": app["alembic_dir"],
                "TESTING": True,
            }
        )
        flask_app.config.update(config or {})
        return flask_app

    return create_app


@pytest.fixture
def flask_app(flask_app_factory: Callable[..., Flask]) -> Flask:
    return flask_app_factory()
