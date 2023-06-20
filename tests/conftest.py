import os
import pathlib
from shutil import copyfile

import alembic
import pytest
from flask import Flask


ROOT = pathlib.Path(__file__).parent.parent


@pytest.fixture
def app(tmpdir):
    db_uri = f"sqlite:///{tmpdir}/database.sqlite"
    alembic_dir = os.path.join(tmpdir, "alembic")
    alembic_cfg = alembic.config.Config(os.path.join(alembic_dir, "alembic.ini"))
    alembic.command.init(alembic_cfg, alembic_dir)
    return {
        "db_uri": db_uri,
        "tmpdir": tmpdir,
        "alembic_dir": alembic_dir,
        "alembic_cfg": alembic_cfg,
    }


@pytest.fixture
def async_enabled_env_script(app):
    copyfile(
        ROOT / "docs" / "aio-env.py.example",
        pathlib.Path(app["alembic_dir"]) / "env.py",
    )


@pytest.fixture
def session(manager):
    with manager.Session() as session:
        yield session


@pytest.fixture
async def async_session(manager):
    async with manager.Session() as session:
        yield session


@pytest.fixture
def flask_client(flask_app):
    with flask_app.test_client() as client:
        with flask_app.app_context():
            yield client


@pytest.fixture
def flask_app_factory(tmpdir, app):
    def create_app(config=None):
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
def flask_app(flask_app_factory):
    return flask_app_factory()
