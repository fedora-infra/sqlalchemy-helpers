# SPDX-FileCopyrightText: 2023 Contributors to the Fedora Project
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import logging
import os

from flask import Flask, jsonify, Response
from sqlalchemy import select

from sqlalchemy_helpers.flask_ext import DatabaseExtension, get_or_404

from .models import AppUser


app = Flask(__name__)
db_path = os.path.normpath(os.path.join(app.root_path, "..", "database.sqlite"))
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.logger.setLevel(logging.INFO)

db = DatabaseExtension()
db.init_app(app)


@app.route("/")
def root() -> Response:
    users = db.session.scalars(select(AppUser)).all()
    return jsonify([u.name for u in users])


@app.route("/user/<int:user_id>")
def user(user_id: int) -> str:
    user = get_or_404(AppUser, user_id)
    return user.name
