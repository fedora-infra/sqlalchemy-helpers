import asyncio
from functools import partial
from unittest import mock

import alembic
import click
import pytest
from click.testing import CliRunner
from pydantic import AnyUrl, BaseModel, ConfigDict, DirectoryPath
from pydantic_settings import BaseSettings

from sqlalchemy_helpers.aio import AsyncDatabaseManager
from sqlalchemy_helpers.fastapi import make_db_session, manager_from_config, syncdb
from sqlalchemy_helpers.manager import exists_in_db

from .models import User  # noqa: F401


@pytest.fixture
def manager(app, async_enabled_env_script):
    return AsyncDatabaseManager(app["db_uri"], app["alembic_dir"])


@pytest.fixture
def settings(app):
    class SQLAlchemyModel(BaseModel):
        url: AnyUrl = AnyUrl("sqlite:///:memory:")
        echo: bool = False

        model_config = ConfigDict(extra="allow")

    class AlembicModel(BaseModel):
        migrations_path: DirectoryPath = app["alembic_dir"]

    class DBModel(BaseModel):
        sqlalchemy: SQLAlchemyModel = SQLAlchemyModel()
        alembic: AlembicModel = AlembicModel()

    class Settings(BaseSettings):
        database: DBModel = DBModel()

    return Settings()


def test_manager_from_config(app, settings):
    settings.database.sqlalchemy.url = AnyUrl("postgresql://db.example.com/dbname")
    manager = manager_from_config(settings.database)
    assert manager.alembic_cfg.get_main_option("script_location") == app["alembic_dir"]
    assert (
        manager.alembic_cfg.get_main_option("sqlalchemy.url")
        == "postgresql://db.example.com/dbname"
    )
    assert str(manager.engine.url) == "postgresql+asyncpg://db.example.com/dbname"


def test_manager_from_config_dict(app, settings):
    manager = manager_from_config(settings.database.model_dump())
    assert manager.alembic_cfg.get_main_option("script_location") == app["alembic_dir"]


async def test_fastapi_syncdb(settings, manager, monkeypatch):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None, partial(alembic.command.revision, manager.alembic_cfg, rev_id="first")
    )
    monkeypatch.setattr(
        "sqlalchemy_helpers.fastapi.manager_from_config",
        mock.Mock(return_value=manager),
    )
    async with manager.engine.connect() as conn:
        assert not (await conn.run_sync(exists_in_db, "users"))
    async with manager.Session() as session:
        assert (await manager.get_current_revision(session)) is None

    @click.command()
    def syncdb_cmd():
        future = asyncio.run_coroutine_threadsafe(syncdb(settings), loop)
        future.result()

    runner = CliRunner()
    result = await loop.run_in_executor(None, runner.invoke, syncdb_cmd)

    assert result.exit_code == 0
    assert result.exception is None

    async with manager.Session() as session:
        assert (await manager.get_current_revision(session)) is not None
    async with manager.engine.connect() as conn:
        assert await conn.run_sync(exists_in_db, "users")
    assert "Database created." in result.output

    result = await loop.run_in_executor(None, runner.invoke, syncdb_cmd)
    assert "Database already up-to-date." in result.output

    await loop.run_in_executor(
        None, partial(alembic.command.revision, manager.alembic_cfg, rev_id="second")
    )
    result = await loop.run_in_executor(None, runner.invoke, syncdb_cmd)
    assert "Database upgraded." in result.output

    mocked_manager = mock.AsyncMock()
    monkeypatch.setattr(
        "sqlalchemy_helpers.fastapi.manager_from_config",
        mock.Mock(return_value=mocked_manager),
    )
    result = await loop.run_in_executor(None, runner.invoke, syncdb_cmd)
    assert "Unexpected sync result:" in result.output


@pytest.fixture
def mocked_manager(manager):
    mock_session = mock.AsyncMock()
    manager.Session = mock.Mock(return_value=mock_session)
    return manager


async def test_make_db_session_success(mocked_manager):
    mock_session = mocked_manager.Session()
    agen = make_db_session(mocked_manager)
    db_session = await agen.asend(None)
    assert db_session is mock_session
    with pytest.raises(StopAsyncIteration):
        await agen.asend(None)
    mock_session.rollback.assert_not_awaited()
    mock_session.close.assert_awaited_with()


async def test_make_db_session_exception(mocked_manager):
    mock_session = mocked_manager.Session()
    agen = make_db_session(mocked_manager)
    db_session = await agen.asend(None)
    assert db_session is mock_session
    with pytest.raises(ValueError):
        await agen.athrow(ValueError("FOO"))
    mock_session.rollback.assert_awaited_with()
    mock_session.close.assert_awaited_with()


async def test_make_db_session_commit_exception(mocked_manager):
    mock_session = mocked_manager.Session()
    mock_session.commit.side_effect = ValueError("BOO")
    agen = make_db_session(mocked_manager)
    db_session = await agen.asend(None)
    assert db_session is mock_session
    with pytest.raises(ValueError):
        await agen.asend(None)
    mock_session.rollback.assert_awaited_with()
    mock_session.close.assert_awaited_with()
