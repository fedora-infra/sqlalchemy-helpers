=============
Release notes
=============

.. towncrier release notes start

v0.11.0
=======

Released on 2023-06-23.
This is a major release that adds AsyncIO and FastAPI support.

Dependency Changes
^^^^^^^^^^^^^^^^^^

* Drop the query_property as it is considered legacy by SQLAlchemy. Instead,
  add :func:`get_by_pk` and :func:`get_one` methods. (:issue:`2702667`).
* Fix compatibility with Flask 2.3 and above (:issue:`6040394`).

Features
^^^^^^^^

* Support for asyncio-based connections, and FastAPI integration
  (:issue:`317`).
* Allow passing extra arguments to `create_engine` and `create_async_engine`
  (:issue:`319`).
