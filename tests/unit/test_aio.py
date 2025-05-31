# SPDX-FileCopyrightText: 2023 Contributors to the Fedora Project
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import asyncio
from collections.abc import AsyncGenerator
from functools import partial
from typing import Any
from unittest import mock

import alembic
import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy_helpers.aio import (
    _async_from_sync_url,
    AsyncDatabaseManager,
    get_by_pk,
    get_or_create,
    update_or_create,
)
from sqlalchemy_helpers.manager import DatabaseStatus, exists_in_db, SyncResult

from .models import AsyncUser


@pytest.fixture
async def manager(
    app: dict[str, str], async_enabled_env_script: None
) -> AsyncGenerator[AsyncDatabaseManager]:
    yield AsyncDatabaseManager(app["db_uri"], app["alembic_dir"])


def test_manager_engine_args(app: dict[str, str], monkeypatch: Any) -> None:
    create_engine = mock.Mock()
    monkeypatch.setattr("sqlalchemy_helpers.aio.create_async_engine", create_engine)
    AsyncDatabaseManager(app["db_uri"], app["alembic_dir"], engine_args={"foo": "bar"})
    create_engine.assert_called_once_with(
        url=make_url(app["db_uri"]).set(drivername="sqlite+aiosqlite"), foo="bar"
    )


async def test_manager_create(manager: AsyncDatabaseManager) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None, partial(alembic.command.revision, manager.alembic_cfg, rev_id="dummy")
    )
    await manager.create()
    async with manager.Session() as session:
        assert (await manager.get_current_revision(session)) == "dummy"
        conn = await session.connection()
        assert await conn.run_sync(exists_in_db, "users_async")


async def test_manager_get_status(manager: AsyncDatabaseManager) -> None:
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
    await loop.run_in_executor(None, alembic.command.stamp, manager.alembic_cfg, "second")
    assert (await manager.get_status()) == DatabaseStatus.UP_TO_DATE


async def test_manager_sync(manager: AsyncDatabaseManager) -> None:
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


async def test_manager_drop(manager: AsyncDatabaseManager) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None, partial(alembic.command.revision, manager.alembic_cfg, rev_id="dummy")
    )
    await manager.create()
    await manager.drop()
    async with manager.engine.connect() as conn:
        assert not (await conn.run_sync(exists_in_db, "users_async"))
    async with manager.Session() as session:
        assert (await manager.get_current_revision(session)) is None


async def test_manager_get_current_revision_no_rev(manager: AsyncDatabaseManager) -> None:
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
def test_async_from_sync_url(in_url: str, out_url_or_exc: str) -> None:
    if isinstance(out_url_or_exc, str):
        assert str(_async_from_sync_url(in_url)) == out_url_or_exc
    else:
        with pytest.raises(out_url_or_exc):
            _async_from_sync_url(in_url)


# Query helpers


async def test_async_get_by_pk(manager: AsyncDatabaseManager, async_session: AsyncSession) -> None:
    await manager.create()
    user = AsyncUser(name="dummy")
    async_session.add(user)
    await async_session.commit()
    user2 = await get_by_pk(user.id, session=async_session, model=AsyncUser)
    assert isinstance(user2, AsyncUser)
    assert user.id == user2.id


async def test_async_get_or_create(
    manager: AsyncDatabaseManager, async_session: AsyncSession
) -> None:
    await manager.create()
    user, created = await get_or_create(async_session, AsyncUser, name="dummy")
    assert created is True
    assert isinstance(user, AsyncUser)
    assert user.name == "dummy"
    user2, created = await get_or_create(async_session, AsyncUser, name="dummy")
    assert created is False
    assert isinstance(user2, AsyncUser)
    assert user.id == user2.id


async def test_get_or_create_property(
    manager: AsyncDatabaseManager, async_session: AsyncSession
) -> None:
    await manager.create()
    user, created = await AsyncUser.get_or_create(async_session, name="dummy")
    assert created is True
    assert user.name == "dummy"
    user2, created = await AsyncUser.get_or_create(async_session, name="dummy")
    assert created is False
    assert user.id == user2.id
    assert user.name == "dummy"
    user2, created = await AsyncUser.get_or_create(async_session, name="dummy")
    assert created is False
    assert user.id == user2.id


async def test_async_update_or_create(
    manager: AsyncDatabaseManager, async_session: AsyncSession
) -> None:
    await manager.create()
    user, created = await update_or_create(
        async_session, AsyncUser, name="dummy", defaults={"full_name": "Dummy"}
    )
    assert created is True
    assert isinstance(user, AsyncUser)
    assert user.name == "dummy"
    assert user.full_name == "Dummy"
    # Now update it
    user2, created = await update_or_create(
        async_session, AsyncUser, name="dummy", defaults={"full_name": "New Value"}
    )
    assert created is False
    assert isinstance(user2, AsyncUser)
    assert user.id == user2.id
    assert user.full_name == "New Value"
    # Test create_defaults
    user3, created = await update_or_create(
        async_session,
        AsyncUser,
        name="dummy2",
        defaults={"full_name": "Wrong Value"},
        create_defaults={"full_name": "Correct Value"},
    )
    assert created is True
    assert user3.name == "dummy2"
    assert user3.full_name == "Correct Value"


async def test_async_update_or_create_property(app: dict[str, str], monkeypatch: Any) -> None:
    session = mock.Mock()
    update_or_create = mock.AsyncMock()
    monkeypatch.setattr("sqlalchemy_helpers.aio.update_or_create", update_or_create)
    manager = AsyncDatabaseManager(app["db_uri"], app["alembic_dir"])
    await manager.create()
    kwargs = dict(
        defaults={"full_name": "Dummy"},
        create_defaults={"full_name": "Initial Dummy"},
    )
    await AsyncUser.update_or_create(session, name="dummy", **kwargs)
    update_or_create.assert_called_once_with(session, model=AsyncUser, name="dummy", **kwargs)
