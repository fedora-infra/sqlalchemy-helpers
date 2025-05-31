# SPDX-FileCopyrightText: 2023 Contributors to the Fedora Project
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import os
import shutil
import sys
from collections.abc import Generator
from typing import Any

import alembic
import pytest

from sqlalchemy_helpers.aio import Base as AsyncBase
from sqlalchemy_helpers.manager import Base


@pytest.fixture
def full_app(tmpdir: str, app: dict[str, Any]) -> Generator[None]:
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
    # Unimport app from previous tests
    for module in list(sys.modules):
        if module == "testapp" or module.startswith("testapp."):
            del sys.modules[module]
    yield
    del os.environ["FLASK_APP"]
    sys.path.remove(str(tmpdir))
    if existing_path is None:
        del os.environ["PYTHONPATH"]
    else:
        os.environ["PYTHONPATH"] = existing_path


@pytest.fixture
def clear_metadata() -> Generator[None]:
    Base.metadata.clear()
    AsyncBase.metadata.clear()
    yield
    Base.metadata.clear()
    AsyncBase.metadata.clear()
