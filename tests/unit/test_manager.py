# SPDX-FileCopyrightText: 2023 Contributors to the Fedora Project
#
# SPDX-License-Identifier: LGPL-3.0-or-later

from typing import Any
from unittest import mock

import alembic
import pytest
from sqlalchemy.orm import Session

from sqlalchemy_helpers.manager import (
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

from .models import User


@pytest.fixture
def manager(app: dict[str, str]) -> DatabaseManager:
    return DatabaseManager(app["db_uri"], app["alembic_dir"])


def test_manager_engine_args(app: dict[str, str], monkeypatch: Any) -> None:
    create_engine = mock.Mock()
    monkeypatch.setattr("sqlalchemy_helpers.manager.create_engine", create_engine)
    DatabaseManager(app["db_uri"], app["alembic_dir"], engine_args={"foo": "bar"})
    create_engine.assert_called_once_with(url=app["db_uri"], foo="bar")


def test_manager_no_revision(manager: DatabaseManager) -> None:
    assert manager.get_latest_revision() is None


def test_manager_get_latest_revision(manager: DatabaseManager) -> None:
    alembic.command.revision(manager.alembic_cfg, rev_id="dummy")
    assert manager.get_latest_revision() == "dummy"


def test_manager_create(manager: DatabaseManager) -> None:
    alembic.command.revision(manager.alembic_cfg, rev_id="dummy")
    manager.create()
    with manager.Session() as session:
        assert manager.get_current_revision(session) == "dummy"


def test_manager_get_status(manager: DatabaseManager) -> None:
    assert manager.get_status() == DatabaseStatus.NO_INFO
    alembic.command.revision(manager.alembic_cfg, rev_id="first")
    manager.create()
    alembic.command.revision(manager.alembic_cfg, rev_id="second")
    assert manager.get_status() == DatabaseStatus.UPGRADE_AVAILABLE
    alembic.command.stamp(manager.alembic_cfg, "second")
    assert manager.get_status() == DatabaseStatus.UP_TO_DATE


def test_manager_sync(manager: DatabaseManager) -> None:
    alembic.command.revision(manager.alembic_cfg, rev_id="first")
    assert manager.sync() == SyncResult.CREATED
    alembic.command.revision(manager.alembic_cfg, rev_id="second")
    assert manager.sync() == SyncResult.UPGRADED
    assert manager.sync() == SyncResult.ALREADY_UP_TO_DATE


def test_manager_drop(manager: DatabaseManager) -> None:
    alembic.command.revision(manager.alembic_cfg, rev_id="dummy")
    manager.create()
    manager.drop()
    with manager.Session() as session:
        assert not exists_in_db(session.get_bind(), "users")
        assert manager.get_current_revision(session) is None


# Query helpers


def test_get_or_create(manager: DatabaseManager, session: Session) -> None:
    manager.create()
    user, created = get_or_create(session, User, name="dummy")
    assert created is True
    assert isinstance(user, User)
    assert user.name == "dummy"
    user2, created = get_or_create(session, User, name="dummy")
    assert created is False
    assert isinstance(user2, User)
    assert user.id == user2.id


def test_get_or_create_property(manager: DatabaseManager, session: Session) -> None:
    manager.create()
    user, created = User.get_or_create(name="dummy")
    assert created is True
    assert user.name == "dummy"
    user2, created = User.get_or_create(name="dummy")
    assert created is False
    assert user.id == user2.id


def test_update_or_create(manager: DatabaseManager, session: Session) -> None:
    manager.create()
    user, created = update_or_create(session, User, name="dummy", defaults={"full_name": "Dummy"})
    assert created is True
    assert isinstance(user, User)
    assert user.name == "dummy"
    assert user.full_name == "Dummy"
    # Now update it
    user2, created = update_or_create(
        session, User, name="dummy", defaults={"full_name": "New Value"}
    )
    assert created is False
    assert isinstance(user2, User)
    assert user.id == user2.id
    assert user.full_name == "New Value"
    # Test create_defaults
    user3, created = update_or_create(
        session,
        User,
        name="dummy2",
        defaults={"full_name": "Wrong Value"},
        create_defaults={"full_name": "Correct Value"},
    )
    assert created is True
    assert user3.name == "dummy2"
    assert user3.full_name == "Correct Value"


def test_update_or_create_property(app: dict[str, str], monkeypatch: Any) -> None:
    update_or_create = mock.Mock()
    monkeypatch.setattr("sqlalchemy_helpers.manager.update_or_create", update_or_create)
    manager = DatabaseManager(app["db_uri"], app["alembic_dir"])
    manager.create()
    kwargs = dict(
        defaults={"full_name": "Dummy"},
        create_defaults={"full_name": "Initial Dummy"},
    )
    User.update_or_create(name="dummy", **kwargs)
    update_or_create.assert_called_once_with(
        session=manager.Session(), model=User, name="dummy", **kwargs
    )


# Migration helpers


def test_exists_in_db(manager: DatabaseManager) -> None:
    manager.create()
    bind = manager.Session.get_bind()
    assert exists_in_db(bind, "users")
    assert exists_in_db(bind, "users", "id")
    assert not exists_in_db(bind, "foobar")
    assert not exists_in_db(bind, "users", "foobar")


def test_is_sqlite(manager: DatabaseManager) -> None:
    assert is_sqlite(manager.Session.get_bind())


def test_get_base_deprecated() -> None:
    with pytest.deprecated_call():
        base = get_base()
    assert base is Base
