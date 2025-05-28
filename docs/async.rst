========================
Asynchronous connections
========================


The sqlalchemy-helpers library supports `AsyncIO connections`_ in SQLAlchemy and Alembic.

.. _AsyncIO connections: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html

All the models must inherit from the :class:`sqlalchemy_helpers.aio.Base` class.


Usage and differences
=====================

The database manager
--------------------

The async-enabled database manager is :class:`sqlalchemy_helpers.aio.AsyncDatabaseManager`.
It can be instanciated with::

    from sqlalchemy_helpers.aio import AsyncDatabaseManager
    db = AsyncDatabaseManager("sqlite:///", "path/to/alembic")

The arguments are the same as the synchronous manager.

Models
------

The base model class can be imported from :class:`sqlalchemy_helpers.aio.Base`. It has the
`AsyncAttrs`_ feature, so you can use the ``awaitable_attrs`` attribute described in the
documentation.

.. _AsyncAttrs: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#sqlalchemy.ext.asyncio.AsyncAttrs


Making queries
--------------

Like the synchronous manager, the async manager has a :attr:`Session <sqlalchemy_helpers.aio.AsyncDatabaseManager.Session>`
property mapping to SQLAlchemy's ``AsyncSession`` factory. Get a session by calling::

    session = db.Session()
    result = await session.execute(select(User).filter_by(name="foo"))
    user = result.one()

The Database Manager will also setup async query methods on your models, similar to the
synchronous versions, but a bit different because you need to provide the session as a
first argument::

    user = await User.get_one(session, name="foo")
    # or
    user = await User.get_by_pk(session, 42)
    # or
    user, created = await User.get_or_create(session, name="foo")
    # or
    user, created = await User.update_or_create(session, name="foo", defaults=dict(full_name="Foo"))


Alembic
-------

You will need to modify Alembic's ``env.py`` script slightly to make it support async operations.
An example is provided in the ``docs/`` directory here in the source code.

You can keep defining your database url with the sync drivers, such as ``sqlite``, ``postgresql``, etc. The database manager will automatically translate them to their async counterparts. As a consequence, you will still be able to use the ``alembic`` command with the sync drivers, as usual.


Migrations
----------

The manager's migration operations are async and will need to be awaited. Besides that,
they work as their synchronous counterparts.


FastAPI integration
===================

This project provides a few FastAPI integration functions.

Making a manager
----------------

The :func:`sqlalchemy_helpers.fastapi.manager_from_config` function will build a
:class:`sqlalchemy_helpers.aio.AsyncDatabaseManager` instance using `Pydantic settings`_

.. _Pydantic settings: https://fastapi.tiangolo.com/advanced/settings/

It assumes a layout such as::

    class SQLAlchemyModel(BaseModel):
        url: stricturl(tld_required=False, host_required=False) = "sqlite:///:memory:"

    class AlembicModel(BaseModel):
        migrations_path: DirectoryPath = Path(__file__).parent.joinpath("migrations").absolute()

    class Settings(BaseSettings):
        sqlalchemy: SQLAlchemyModel = SQLAlchemyModel()
        alembic: AlembicModel = AlembicModel()

You can, of course, pass a subset of the configuration to the function.
It also understands plain dictionaries.


Sync CLI
--------

A function wrapping the manager's ``sync`` method is provided in
:func:`sqlalchemy_helpers.fastapi.syncdb`. You can hook it up to your click-based CLI,
it takes the Pydantic settings as only argument.


Base setup
----------

The library provides functions that you can use as a dependencies in your FastAPI path operations.
First, create a python module to integrate those functions with your Pydantic settings::

    # database.py

    from collections.abc import AsyncIterator
    from fastapi import APIRouter, Depends
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy_helpers.fastapi import AsyncDatabaseManager, make_db_session, manager_from_config
    from sqlalchemy_helpers.aio import Base
    from .config import get_settings
    from . import models

    async def gen_db_manager() -> AsyncDatabaseManager:
        db_settings = get_settings().database
        return manager_from_config(db_settings)

    async def gen_db_session(
        db_manager: AsyncDatabaseManager = Depends(gen_db_manager),
    ) -> AsyncIterator[AsyncSession]:
        async for session in make_db_session(db_manager):
            yield session


We also recommend re-exporting the :class:`sqlalchemy_helpers.aio.Base` class for
convenience and ease of refactoring.

In the main module, declare the application. This example uses routers for modularity::

    # main.py

    from fastapi import FastAPI
    from .views import router

    app = FastAPI()
    app.include_router(router)


Models
------

You can declare your models as you usually would with SQLAlchemy, just inherit from the
:class:`Base` class that you re-exported in ``database.py``::

    # models.py

    from sqlalchemy import UnicodeText
    from sqlalchemy.orm import Mapped, mapped_column
    from .database import Base

    class User(Base):
        __tablename__ = "users"

        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str] = mapped_column(UnicodeText, unique=True)

Note: these models do not depend on the FastAPI extension, only the main part of sqlalchemy-helpers.
They will import and work just fine without FastAPI.

Also note that if you want to move your models away from sqlalchemy-helpers and back to plain
SQLAlchemy, all you have to do is replace the :class:`Base` import with::

    from sqlalchemy.orm import DeclarativeBase

    Base = DecalarativeBase()


Access in path operations
-------------------------

Now, you can use FastAPI's dependency injection to get the database session in your path operations::

    # views.py

    from fastapi import APIRouter, Depends
    from .database import gen_db_session
    from .models import User

    router = APIRouter(prefix="/users")

    @router.get("/user/{name}")
    async def get_user(name: str, db_session: AsyncSession = Depends(gen_db_session)):
        user = await User.get_one(db_session, name=name)
        return user


Migrations
----------

You can adjust alembic's ``env.py`` file to get the database URL from your app's configuration::

    # migrations/env.py

    from my_fastapi_app.config import get_settings
    from my_fastapi_app.database import Base

    url = get_settings().database.sqlalchemy.url
    config.set_main_option("sqlalchemy.url", url)
    target_metadata = Base.metadata

    # ...rest of the env.py file...

Also set ``script_location`` in you ``alembic.ini`` file in order to use it with the ``alembic``
command-line tool::

    # migrations/alembic.ini

    [alembic]
    script_location = %(here)s
