# SPDX-FileCopyrightText: 2023 Contributors to the Fedora Project
#
# SPDX-License-Identifier: LGPL-3.0-or-later

from sqlalchemy import Unicode
from sqlalchemy.orm import Mapped, mapped_column

from sqlalchemy_helpers.aio import Base as AsyncBase
from sqlalchemy_helpers.manager import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(254), index=True, unique=True)
    full_name: Mapped[str | None]


class AsyncUser(AsyncBase):
    __tablename__ = "users_async"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(254), index=True, unique=True)
    full_name: Mapped[str | None]
