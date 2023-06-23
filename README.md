# SQLAlchemy Helpers

This project contains a tools to use SQLAlchemy and Alembic in a project.

It has a Flask integration, and other framework integrations could be added in the future.

The full documentation is [on ReadTheDocs](https://sqlalchemy-helpers.readthedocs.io).

You can install it [from PyPI](https://pypi.org/project/sqlalchemy-helpers/).

![PyPI](https://img.shields.io/pypi/v/sqlalchemy-helpers.svg)
![Supported Python versions](https://img.shields.io/pypi/pyversions/sqlalchemy-helpers.svg)
![Tests status](https://github.com/fedora-infra/sqlalchemy-helpers/actions/workflows/tests.yml/badge.svg?branch=develop)
![Documentation](https://readthedocs.org/projects/sqlalchemy-helpers/badge/?version=latest)

## Features

Here's what sqlalchemy-helpers provides:

- Alembic integration:
  - programmatically create or upgrade your schema,
  - get information about schema versions and status
  - drop your tables without leaving alembic information behind
  - use a function in your `env.py` script to retrieve the database URL, and
    thus avoid repeating your configuration in two places.
  - migration helper functions such as `is_sqlite()` or `exists_in_db()`
- SQLAlchemy naming convention for easier schema upgrades
- Automatically activate foreign keys on SQLite
- Addition of some useful query properties on your models
- A query function `get_or_create()` that you can call directly or use on your model classes
- Optional Flask integration: you can use sqlalchemy-helpers outside of a Flask app and feel at home
- The models created with sqlalchemy-helpers work both inside and outside the Flask application
  context
- Support for asyncio and FastAPI.

This project has 100% code coverage and aims at reliably sharing some of the basic boilerplate
between applications that use SQLAlchemy.

Check out the [User Guide](https://sqlalchemy-helpers.readthedocs.io/en/latest/user.html) to learn
how to use it in your application, with or without a web framework.

## FAQ

- Why not use [Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com) and
  [Flask-Migrate](https://github.com/miguelgrinberg/Flask-Migrate/)?

Those projects are great, but we also have apps that are not based on Flask and that would benefit
from the features provided by sqlalchemy-helpers.
