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

If you need to, you can have a different base class for your models, using the
:func:`sqlalchemy_helpers.manager.get_base` function::

    from sqlalchemy_helpers import get_base

    Base = get_base(cls=CustomBase)

All the arguments passed to the :func:`~sqlalchemy_helpers.manager.get_base` function will be
transferred to the :func:`sqlalchemy.orm.declarative_base` function.

The database manager
--------------------

Most of the integration work in sqlalchemy-helpers is done via the
:class:`sqlalchemy_helpers.manager.DatabaseManager`. It can be instanciated with::

    from sqlalchemy_helpers import DatabaseManager
    db = DatabaseManager("sqlite:///", "path/to/alembic")

The first argument is the database URI, the second argument is the path to the alembic directory is
where Alembic's ``env.py`` resides. The third argument is a dictionary of additional keyword
arguments that will be passed to the ``create_engine`` factory along with the URI. The fourth
argument is the custom base class, if you have defined any (it is optional).

You can call the Database Manager's functions to get information about your database or to migrate
its schema.

Making queries
--------------

The Database Manager has a :attr:`Session <sqlalchemy_helpers.manager.DatabaseManager.Session>`
property mapping to SQLAlchemy's ``Session`` factory, scoped for multithreading use. Get a session
by calling::

    session = db.Session()
    user = session.query(User).filter_by(name="foo").one()

This library also provides a :func:`get_or_create() <sqlalchemy_helpers.manager.get_or_create>`
function, as popularized by Django::

    from sqlalchemy_helpers import get_or_create

    user, created = get_or_create(User, name="foo")

For convenience, this function is also available as a model method::

    user, created = User.get_or_create(name="foo")

Other useful model methods are::

    user = User.get_one(name="foo")
    user = User.get_by_pk(42)


Migrations
----------

The manager can create and update your database. It also has a :meth:`sync()
<sqlalchemy_helpers.manager.DatabaseManager.sync>` method that will create the database if it does
not exist or update it if it is not at the latest schema revision. The :meth:`sync()
<sqlalchemy_helpers.manager.DatabaseManager.sync>` call will return the result of the operation as a
member of the :class:`SyncResult <sqlalchemy_helpers.SyncResult>` enum so you can react
accordingly.

You can also find a couple helper functions for your migrations: :func:`is_sqlite()
<sqlalchemy_helpers.manager.is_sqlite>` and :func:`exists_in_db()
<sqlalchemy_helpers.manager.exists_in_db>`.


Flask integration
=================

This project provides a Flask integration layer for Flask >= 2.0.0. This is
how you can use it.

Base setup
----------

First, create a python module to instanciate the :class:`DatabaseExtension
<sqlalchemy_helpers.flask_ext.DatabaseExtension>`, and re-export some useful helpers::

    # database.py

    from sqlalchemy_helpers import Base, get_or_create, is_sqlite, exists_in_db
    from sqlalchemy_helpers.flask_ext import DatabaseExtension, get_or_404, first_or_404

    db = DatabaseExtension()

In the application factory, import the instance and call its :class:`init_app()
<sqlalchemy_helpers.flask_ext.DatabaseExtension.init_app>` method::

    # app.py

    from flask import Flask
    from .database import db

    def create_app():
        """See https://flask.palletsprojects.com/en/1.1.x/patterns/appfactories/"""

        app = Flask(__name__)

        # Load the optional configuration file
        if "FLASK_CONFIG" in os.environ:
            app.config.from_envvar("FLASK_CONFIG")

        # Database
        db.init_app(app)

        return app

If you need to define a custom base class, you can pass it to the extension using the
``base_model`` argument of the
:meth:`~sqlalchemy_helpers.flask_ext.DatabaseExtension.__init__` constructor or the
:meth:`~sqlalchemy_helpers.flask_ext.DatabaseExtension.init_app` function.


Models
------

You can declare your models as you usually would with SQLAlchemy, just inherit from the
:class:`Base` class that you re-exported in ``database.py``::

    # models.py

    from sqlalchemy import Column, Integer, Unicode

    from .database import Base


    class User(Base):

        __tablename__ = "users"

        id = Column("id", Integer, primary_key=True)
        name = Column(Unicode(254), index=True, unique=True, nullable=False)
        full_name = Column(Unicode(254), nullable=False)
        timezone = Column(Unicode(127), nullable=True)

Note: these models do not depend on the Flask extension, only the main part of sqlalchemy-helpers.
They will import and work just fine without Flask.

Also note that if you want to move your models away from sqlalchemy-helpers and back to plain
SQLAlchemy, all you have to do is replace the :class:`Base` import with::

    from sqlalchemy.orm import declarative_base

    Base = decalarative_base()


Views
-----

Now in your views, you can use the instance's :attr:`session` property to access the SQLAlchemy
session object. There are also functions to ease classical view patterns such as getting an object
by ID or returning a 404 error if not found::

    # views.py

    from .database import db, get_or_404
    from .models import User


    @bp.route("/")
    def root():
        users = db.session.query(User).all()
        return render_template("index.html", users=users)


    @bp.route("/user/<int:user_id>")
    def profile(user_id):
        user = get_or_404(User, user_id)
        return render_template("profile.html", user=user)


Migrations
----------

You can adjust alembic's ``env.py`` file to get the database URL from your app's configuration::

    # migrations/env.py

    from my_flask_app.app import create_app
    from my_flask_app.database import Base
    from sqlalchemy_helpers.flask_ext import get_url_from_app

    url = get_url_from_app(create_app)
    config.set_main_option("sqlalchemy.url", url)
    target_metadata = Base.metadata

    # ...rest of the env.py file...

Also set ``script_location`` in you ``alembic.ini`` file in order to use it with the ``alembic``
command-line tool::

    # migrations/alembic.ini

    [alembic]
    script_location = %(here)s


Features summary
----------------

And that's it! You'll gain the following features:

- a per-request session you can use with :attr:`db.session`
- recursive auto-import of your models
- a ``db`` subcommand to sync your models: just run ``flask db sync``
- two view utility functions: :func:`get_or_404() <sqlalchemy_helpers.flask_ext.get_or_404>` and
  :func:`first_or_404() <sqlalchemy_helpers.flask_ext.first_or_404>`, which let you query the
  database and return 404 errors if the expected record is not found
- the ``alembic`` command is still functional as documented upstream by pointing at the
  ``alembic.ini`` file

Full example
------------

In Fedora Infrastructure we use a `cookiecutter template`_ that showcases this Flask
integration, feel free to check it out or even use it if it suits your needs.

.. _cookiecutter template: https://github.com/fedora-infra/cookiecutter-flask-webapp/

Openshift health checks
-----------------------

Being able to programmatically know whether the database schema is up-to-date is very useful when
working with cloud services that check that your application is actually available, such as
OpenShift/Kubernetes. If you're using `flask-healthz`_ you can write a pretty clever readiness
function such as::

    from flask_healthz import HealthError
    from sqlalchemy_helpers import DatabaseStatus
    from .database import db

    def liveness():
        pass

    def readiness():
        try:
            status = db.manager.get_status()
        except Exception as e:
            raise HealthError(f"Can't get the database status: {e}")
        if status is DatabaseStatus.NO_INFO:
            raise HealthError("Can't connect to the database")
        if status is DatabaseStatus.UPGRADE_AVAILABLE:
            raise HealthError("The database schema needs to be updated")

With this function, OpenShift will not forward requests to the updated version of your application
if there are pending schema changes, and will keep serving from the old version until you've applied
the database migration.

.. _flask-healthz: https://github.com/fedora-infra/flask-healthz/
