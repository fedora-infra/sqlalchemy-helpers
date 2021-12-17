import os
import shutil
import sys

import alembic
import pytest


@pytest.fixture
def full_app(tmpdir, app):
    app_dir = os.path.join(tmpdir, "testapp")
    shutil.copytree(os.path.join(os.path.dirname(__file__), "app_fixture"), app_dir)
    # alembic setup
    alembic_dir = os.path.join(app_dir, "migrations")
    alembic_cfg = alembic.config.Config(os.path.join(alembic_dir, "alembic.ini"))
    alembic.command.init(alembic_cfg, alembic_dir)
    alembic.command.revision(alembic_cfg, rev_id="initial")
    # Don't change the logging configuration
    os.rename(
        os.path.join(app_dir, "migrations", "env.py"),
        os.path.join(app_dir, "migrations", "env.py_"),
    )
    with open(os.path.join(app_dir, "migrations", "env.py"), "w") as dest:
        with open(os.path.join(app_dir, "migrations", "env.py_")) as src:
            for line in src:
                if line.startswith("fileConfig"):
                    continue
                dest.write(line)
    # Prepare the environment
    sys.path.insert(0, str(tmpdir))
    os.environ["FLASK_APP"] = "testapp.app"
    existing_path = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = os.pathsep.join(
        [str(tmpdir)] + (existing_path.split(os.pathsep) if existing_path else [])
    )
    yield
    del os.environ["FLASK_APP"]
    sys.path.remove(str(tmpdir))
    if existing_path is None:
        del os.environ["PYTHONPATH"]
    else:
        os.environ["PYTHONPATH"] = existing_path
