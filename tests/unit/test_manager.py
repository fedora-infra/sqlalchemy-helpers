from unittest import mock

import alembic
import pytest

from sqlalchemy_helpers.manager import (
    DatabaseManager,
    DatabaseStatus,
    exists_in_db,
    get_or_create,
    is_sqlite,
    SyncResult,
)

from .models import User


@pytest.fixture
def manager(app):
    return DatabaseManager(app["db_uri"], app["alembic_dir"])


def test_manager_engine_args(app, monkeypatch):
    create_engine = mock.Mock()
    monkeypatch.setattr("sqlalchemy_helpers.manager.create_engine", create_engine)
    DatabaseManager(app["db_uri"], app["alembic_dir"], {"foo": "bar"})
    create_engine.assert_called_once_with(url=app["db_uri"], foo="bar")


def test_manager_no_revision(manager):
    assert manager.get_latest_revision() is None


def test_manager_get_latest_revision(manager):
    alembic.command.revision(manager.alembic_cfg, rev_id="dummy")
    assert manager.get_latest_revision() == "dummy"


def test_manager_create(manager):
    alembic.command.revision(manager.alembic_cfg, rev_id="dummy")
    manager.create()
    with manager.Session() as session:
        assert manager.get_current_revision(session) == "dummy"


def test_manager_get_status(manager):
    assert manager.get_status() == DatabaseStatus.NO_INFO
    alembic.command.revision(manager.alembic_cfg, rev_id="first")
    manager.create()
    alembic.command.revision(manager.alembic_cfg, rev_id="second")
    assert manager.get_status() == DatabaseStatus.UPGRADE_AVAILABLE
    alembic.command.stamp(manager.alembic_cfg, "second")
    assert manager.get_status() == DatabaseStatus.UP_TO_DATE


def test_manager_sync(manager):
    alembic.command.revision(manager.alembic_cfg, rev_id="first")
    assert manager.sync() == SyncResult.CREATED
    alembic.command.revision(manager.alembic_cfg, rev_id="second")
    assert manager.sync() == SyncResult.UPGRADED
    assert manager.sync() == SyncResult.ALREADY_UP_TO_DATE


def test_manager_drop(manager):
    alembic.command.revision(manager.alembic_cfg, rev_id="dummy")
    manager.create()
    manager.drop()
    with manager.Session() as session:
        assert not exists_in_db(session.get_bind(), "users")
        assert manager.get_current_revision(session) is None


# Query helpers


def test_get_or_create(manager, session):
    manager.create()
    user, created = get_or_create(session, User, name="dummy")
    assert created is True
    assert isinstance(user, User)
    assert user.name == "dummy"
    user2, created = get_or_create(session, User, name="dummy")
    assert created is False
    assert isinstance(user2, User)
    assert user.id == user2.id


def test_get_or_create_property(manager, session):
    manager.create()
    user, created = User.get_or_create(name="dummy")
    assert created is True
    assert user.name == "dummy"
    user2, created = User.get_or_create(name="dummy")
    assert created is False
    assert user.id == user2.id


# Migration helpers


def test_exists_in_db(manager):
    manager.create()
    bind = manager.Session.get_bind()
    assert exists_in_db(bind, "users")
    assert exists_in_db(bind, "users", "id")
    assert not exists_in_db(bind, "foobar")
    assert not exists_in_db(bind, "users", "foobar")


def test_is_sqlite(manager):
    assert is_sqlite(manager.Session.get_bind())
