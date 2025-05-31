# SPDX-FileCopyrightText: 2023 Contributors to the Fedora Project
#
# SPDX-License-Identifier: LGPL-3.0-or-later

from functools import partial
from typing import Any, Callable

import alembic
import pytest
from flask import Flask, jsonify, Response
from flask.testing import FlaskClient
from sqlalchemy import select

from sqlalchemy_helpers.flask_ext import (
    DatabaseExtension,
    first_or_404,
    get_or_404,
    get_url_from_app,
)
from sqlalchemy_helpers.manager import DatabaseManager, exists_in_db

from .models import User


def make_user(db: DatabaseExtension, name: str) -> User:
    user = User(name=name)
    db.session.add(user)
    db.session.commit()
    return user


def test_flask_ext_basic_view(flask_app: Flask, flask_client: FlaskClient) -> None:
    db = DatabaseExtension(flask_app)
    db.manager.create()
    make_user(db, "dummy")

    @flask_app.route("/")
    def view() -> Response:
        users = db.session.scalars(select(User)).all()
        return jsonify([u.name for u in users])

    response = flask_client.get("/")
    assert response.json == ["dummy"]


def test_flask_ext_get_or_404(flask_app: Flask, flask_client: FlaskClient) -> None:
    db = DatabaseExtension(flask_app)
    db.manager.create()
    user = make_user(db, "dummy")

    @flask_app.route("/user/<int:user_id>")
    def view(user_id: int) -> str:
        user = get_or_404(User, user_id)
        return user.name

    response = flask_client.get(f"/user/{user.id}")
    assert response.data == b"dummy"

    response = flask_client.get(f"/user/{user.id + 1}")
    assert response.status_code == 404


def test_flask_ext_first_or_404(flask_app: Flask, flask_client: FlaskClient) -> None:
    db = DatabaseExtension(flask_app)
    db.manager.create()
    user = make_user(db, "dummy")

    @flask_app.route("/user/<name>")
    def view(name: str) -> Response:
        user = first_or_404(select(User).filter_by(name=name), "no such user")
        return jsonify(user.id)

    response = flask_client.get("/user/dummy")
    assert response.json == user.id

    response = flask_client.get("/user/nobody")
    assert response.status_code == 404
    assert "<p>no such user</p>" in response.get_data(as_text=True)


def test_flask_ext_first_or_404_custom_session(app: dict[str, str]) -> None:
    manager = DatabaseManager(app["db_uri"], app["alembic_dir"])
    manager.create()
    session = manager.Session()
    session.add(User(name="dummy"))
    session.commit()
    try:
        first_or_404(select(User).filter_by(name="dummy"), "no such user", session=session)
    except RuntimeError as e:
        # If no session is given, calling current_app outside the app context will raise RuntimeError
        pytest.fail(str(e))


def test_flask_ext_script(flask_app: Flask, mocker: Any) -> None:
    db = DatabaseExtension(flask_app)
    with flask_app.app_context():
        alembic.command.revision(db.manager.alembic_cfg, rev_id="dummy")
        assert not exists_in_db(db.session.get_bind(), "users")
        assert db.manager.get_current_revision(db.session) is None
    assert "db" in flask_app.cli.commands
    assert "sync" in flask_app.cli.commands["db"].commands  # type: ignore
    sync_cmd = flask_app.cli.commands["db"].commands["sync"]  # type: ignore
    runner = flask_app.test_cli_runner()
    result = runner.invoke(sync_cmd)
    with flask_app.app_context():
        assert exists_in_db(db.session.get_bind(), "users")
        assert db.manager.get_current_revision(db.session) is not None
    assert "Database created." in result.output
    result = runner.invoke(sync_cmd)
    assert "Database already up-to-date." in result.output
    with flask_app.app_context():
        alembic.command.revision(db.manager.alembic_cfg, rev_id="second")
    result = runner.invoke(sync_cmd)
    assert "Database upgraded." in result.output
    mocker.patch("sqlalchemy_helpers.flask_ext._get_manager")
    result = runner.invoke(sync_cmd)
    assert "Unexpected sync result:" in result.output


def test_flask_ext_get_url(flask_app_factory: Callable[..., Flask]) -> None:
    factory = partial(
        flask_app_factory, {"SQLALCHEMY_DATABASE_URI": "sqlite:////outside/app/context"}
    )
    assert get_url_from_app(factory) == "sqlite:////outside/app/context"

    flask_app = flask_app_factory({"SQLALCHEMY_DATABASE_URI": "sqlite:////inside/app/context"})
    with flask_app.app_context():
        assert get_url_from_app(factory) == "sqlite:////inside/app/context"
