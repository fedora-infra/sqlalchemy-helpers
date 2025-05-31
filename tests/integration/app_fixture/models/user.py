# SPDX-FileCopyrightText: 2023 Contributors to the Fedora Project
#
# SPDX-License-Identifier: LGPL-3.0-or-later

from sqlalchemy.orm import Mapped, mapped_column

from sqlalchemy_helpers.manager import Base


class AppUser(Base):
    __tablename__ = "app_users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
