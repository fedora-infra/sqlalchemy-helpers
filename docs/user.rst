==========
User Guide
==========


Standalone
==========

Even without a framework extension, sqlalchemy-helpers brings many interesting features. Here's how
you can use it.

Writing models
--------------

All the models must inherit from the :class:`sqlalchemy_helpers.manager.Base` class. It is
equivalent to SQLAlchemy's ``declarative_base()`` with a constraint naming convention and some extra
features.

Example::

    from sqlalchemy import Column, Integer, Unicode
    from sqlalchemy_helpers import Base

    class User(Base):

        __tablename__ = "users"

        id = Column("id", Integer, primary_key=True)
        name = Column(Unicode(254), index=True, unique=True, nullable=False)
        full_name = Column(Unicode(254), nullable=False)
        timezone = Column(Unicode(127), nullable=True)

As you can see, it is very similar to what you would do with plain SQLAlchemy.


The database manager
--------------------

Most of the integration work in sqlalchemy-helpers is done via the
:class:`sqlalchemy_helpers.manager.DatabaseManager`. It can be instanciated with::

    from sqlalchemy_helpers import DatabaseManager
    db = DatabaseManager("sqlite:///", "path/to/alembic")

The first argument is the database URI, the second argument is the path to the alembic directory is
where Alembic's ``env.py``.resides. You can call the Database Manager's functions to get information
about your database or to migrate its schema.

Making queries
--------------

The Database Manager has a :attr:`Session <sqlalchemy_helpers.manager.DatabaseManager.Session>`
property mapping to SQLAlchemy's ``Session`` factory, scoped for multithreading use. Get a session
by calling::

    session = db.Session()
    user = session.query(User).filter_by(name="foo").one()

The Database Manager will also setup a query property on you models, so you can make queries like::

    user = User.query.filter_by(name="foo").one()

This library also provides a :func:`get_or_create() <sqlalchemy_helpers.manager.get_or_create>`
function, as popularized by Django::

    from sqlalchemy_helpers import get_or_create

    user, created = get_or_create(User, name="foo")

For convenience, this function is also available as a model method::

    user, created = User.get_or_create(name="foo")


Migrations
----------

The manager can create and update your database. It also has a :meth:`sync()
<sqlalchemy_helpers.manager.DatabaseManager.sync>` method that will create the database if it does
not exist or update it if it is not at the latest schema revision. The :meth:`sync()
<sqlalchemy_helpers.manager.DatabaseManager.sync>` call will return the result of the operation as a
member of the :class:`SyncResult <sqlalchemy_helpers.manager.SyncResult>` enum so you can react
accordingly.

You can also find a couple helper functions for your migrations: :func:`is_sqlite()
<sqlalchemy_helpers.manager.is_sqlite>` and :func:`exists_in_db()
<sqlalchemy_helpers.manager.exists_in_db>`.
