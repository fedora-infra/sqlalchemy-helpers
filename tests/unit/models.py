# SPDX-FileCopyrightText: 2023 Contributors to the Fedora Project
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import sqlalchemy as sa

from sqlalchemy_helpers.manager import Base


class User(Base):
    __tablename__ = "users"

    id = sa.Column("id", sa.Integer, primary_key=True)
    name = sa.Column(sa.Unicode(254), index=True, unique=True, nullable=False)
    full_name = sa.Column(sa.Unicode(254), nullable=True)
