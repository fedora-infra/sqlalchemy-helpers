import asyncio
from functools import partial
from unittest import mock

import alembic
import pytest
from sqlalchemy.engine import make_url

from sqlalchemy_helpers.aio import (
    _async_from_sync_url,
    AsyncDatabaseManager,
    get_by_pk,
    get_or_create,
)
from sqlalchemy_helpers.manager import DatabaseStatus, exists_in_db, SyncResult

from .models import User


@pytest.fixture
async def manager(app, async_enabled_env_script):
    yield AsyncDatabaseManager(app["db_uri"], app["alembic_dir"])


def test_manager_engine_args(app, monkeypatch):
    create_engine = mock.Mock()
    monkeypatch.setattr("sqlalchemy_helpers.aio.create_async_engine", create_engine)
    AsyncDatabaseManager(app["db_uri"], app["alembic_dir"], {"foo": "bar"})
    create_engine.assert_called_once_with(
        url=make_url(app["db_uri"]).set(drivername="sqlite+aiosqlite"), foo="bar"
    )


async def test_manager_create(manager):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None, partial(alembic.command.revision, manager.alembic_cfg, rev_id="dummy")
    )
    await manager.create()
    async with manager.Session() as session:
        assert (await manager.get_current_revision(session)) == "dummy"
        conn = await session.connection()
        assert await conn.run_sync(exists_in_db, "users")


async def test_manager_get_status(manager):
    loop = asyncio.get_running_loop()
    assert (await manager.get_status()) == DatabaseStatus.NO_INFO
    await loop.run_in_executor(
        None, partial(alembic.command.revision, manager.alembic_cfg, rev_id="first")
    )
    await manager.create()
    await loop.run_in_executor(
        None, partial(alembic.command.revision, manager.alembic_cfg, rev_id="second")
    )
    assert (await manager.get_status()) == DatabaseStatus.UPGRADE_AVAILABLE
    await loop.run_in_executor(
        None, alembic.command.stamp, manager.alembic_cfg, "second"
    )
    assert (await manager.get_status()) == DatabaseStatus.UP_TO_DATE


async def test_manager_sync(manager):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None, partial(alembic.command.revision, manager.alembic_cfg, rev_id="first")
    )
    assert (await manager.sync()) == SyncResult.CREATED
    await loop.run_in_executor(
        None, partial(alembic.command.revision, manager.alembic_cfg, rev_id="second")
    )
    assert (await manager.sync()) == SyncResult.UPGRADED
    assert (await manager.sync()) == SyncResult.ALREADY_UP_TO_DATE


async def test_manager_drop(manager):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None, partial(alembic.command.revision, manager.alembic_cfg, rev_id="dummy")
    )
    await manager.create()
    await manager.drop()
    async with manager.engine.connect() as conn:
        assert not (await conn.run_sync(exists_in_db, "users"))
    async with manager.Session() as session:
        assert (await manager.get_current_revision(session)) is None


async def test_manager_get_current_revision_no_rev(manager):
    await manager.create()
    async with manager.Session() as session:
        assert (await manager.get_current_revision(session)) is None


# URL translation


@pytest.mark.parametrize(
    "in_url, out_url_or_exc",
    (
        ("sqlite:///fmn.db", "sqlite+aiosqlite:///fmn.db"),
        ("sqlite+foo:///fmn.db", "sqlite+aiosqlite:///fmn.db"),
        ("postgresql:///fmn", "postgresql+asyncpg:///fmn"),
        ("postgresql+pg8000:///fmn", "postgresql+asyncpg:///fmn"),
        ("mysql:///fmn", "mysql+aiomysql:///fmn"),
        ("unknowndb:///fmn", ValueError),
    ),
)
def test_async_from_sync_url(in_url, out_url_or_exc):
    if isinstance(out_url_or_exc, str):
        assert str(_async_from_sync_url(in_url)) == out_url_or_exc
    else:
        with pytest.raises(out_url_or_exc):
            _async_from_sync_url(in_url)


# Query helpers


async def test_async_get_by_pk(manager, async_session):
    await manager.create()
    user = User(name="dummy")
    async_session.add(user)
    await async_session.commit()
    user2 = await get_by_pk(user.id, session=async_session, model=User)
    assert isinstance(user2, User)
    assert user.id == user2.id


async def test_async_get_or_create(manager, async_session):
    await manager.create()
    user, created = await get_or_create(async_session, User, name="dummy")
    assert created is True
    assert isinstance(user, User)
    assert user.name == "dummy"
    user2, created = await get_or_create(async_session, User, name="dummy")
    assert created is False
    assert isinstance(user2, User)
    assert user.id == user2.id


async def test_get_or_create_property(manager, async_session):
    await manager.create()
    user, created = await User.get_or_create(async_session, name="dummy")
    assert created is True
    assert user.name == "dummy"
    user2, created = await User.get_or_create(async_session, name="dummy")
    assert created is False
    assert user.id == user2.id
    assert user.name == "dummy"
    user2, created = await User.get_or_create(async_session, name="dummy")
    assert created is False
    assert user.id == user2.id
