import sqlalchemy as sa

from sqlalchemy_helpers import Base


class AppUser(Base):
    __tablename__ = "app_users"
    id = sa.Column("id", sa.Integer, primary_key=True)
    name = sa.Column(sa.Unicode(254), nullable=False)
