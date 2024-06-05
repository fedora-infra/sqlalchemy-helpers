# Release notes

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This project uses [_towncrier_](https://towncrier.readthedocs.io/) and the changes for the upcoming release can be found in <https://github.com/fedora-infra/sqlalchemy-helpers/tree/develop/news/>.

<!-- towncrier release notes start -->

## Version [1.0.1](https://github.com/fedora-infra/sqlalchemy-helpers/tree/v1.0.1)

Released on 2024-06-05. This is a bugfix release.

### Bug Fixes

- Don't include the tests when installing the package with pip ([685b92a](https://github.com/fedora-infra/sqlalchemy-helpers/commits/685b92a))

### Development Improvements

- Add generic pre-commit checks ([6d9dffd](https://github.com/fedora-infra/sqlalchemy-helpers/commits/6d9dffd))
- Adjust Ruff and Black config ([5c3b7f4](https://github.com/fedora-infra/sqlalchemy-helpers/commits/5c3b7f4))
- Set the licenses headers with Reuse ([acbdf96](https://github.com/fedora-infra/sqlalchemy-helpers/commits/acbdf96))



## Version [1.0.0](https://github.com/fedora-infra/sqlalchemy-helpers/tree/v1.0.0)

Released on 2024-05-30. This is a feature release.

### Features

- Add an `update_or_create()` function similar to Django's (#422)
- Allow `aio.manager_from_config()` to pass arguments to the `AsyncDatabaseManager`
- Allow a few methods to use an existing session ([993e6a5](https://github.com/fedora-infra/sqlalchemy-helpers/commits/993e6a5)).
- Officially support Python 3.12 ([7b88ef7](https://github.com/fedora-infra/sqlalchemy-helpers/commits/7b88ef7)).
- The `engine_args` and `base_model` arguments must now be keywords ([abaccdc](https://github.com/fedora-infra/sqlalchemy-helpers/commits/abaccdc)).

## Version [0.13.0](https://github.com/fedora-infra/sqlalchemy-helpers/tree/v0.13.0)

Released on 2023-11-16. This is a feature release that adds customization of the model base class.

### Features

- Allow customization of the model base class
  ([bc26cd3](https://github.com/fedora-infra/sqlalchemy-helpers/commits/bc26cd3)).

## Version [0.12.1](https://github.com/fedora-infra/sqlalchemy-helpers/tree/v0.12.1)

Released on 2023-10-12. This is a minor release that adds docs and development improvements

### Development Improvements

- Automatically publish to PyPI and release
  ([c572657](https://github.com/fedora-infra/sqlalchemy-helpers/commits/c572657)).

### Documentation Improvements

- Release notes: show dependency changes further down the page
  ([499ec7a](https://github.com/fedora-infra/sqlalchemy-helpers/commits/499ec7a)).
- Convert the release notes to Markdown
  ([841e1fb](https://github.com/fedora-infra/sqlalchemy-helpers/commits/841e1fb)).

## Version 0.12.0

Released on 2023-08-09.
This is a feature release that adds MySQL/MariaDB support in the async mode.

### Features

- Add support for MySQL/MariaDB in the async mode (#325).

### Bug Fixes

- The psycopg driver raises a ProgrammingError where sqlite raises an
  OperationalError ([469d9c7](https://github.com/fedora-infra/sqlalchemy-helpers/commit/469d9c7)).

### Dependency Changes

- Fix a minor compatibility issue with SQLAlchemy 2.0 ([3f379e2](https://github.com/fedora-infra/sqlalchemy-helpers/commit/3f379e2)).
- Support Pydantic 2.0+ and Pydantic Settings (#323).

## Version 0.11.0

Released on 2023-06-23.
This is a major release that adds AsyncIO and FastAPI support.

### Dependency Changes

- Drop the `query_property` as it is considered legacy by SQLAlchemy. Instead,
  add `get_by_pk()` and `get_one()` methods ([2702667](https://github.com/fedora-infra/sqlalchemy-helpers/commit/2702667)).
- Fix compatibility with Flask 2.3 and above ([6040394](https://github.com/fedora-infra/sqlalchemy-helpers/commit/6040394)).

### Features

- Support for asyncio-based connections, and FastAPI integration (#317).
- Allow passing extra arguments to `create_engine()` and `create_async_engine()` (#319).
