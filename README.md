# SQLAlchemy Helpers

This project contains a tools to use SQLAlchemy and Alembic in a project.

It has a Flask integration, and other framework integrations could be added in
the future.


## Flask integration

This is how you can use the Flask integration.

First, create a python module to instanciate the `DatabaseExtension`, and
re-export some useful helpers:

```python
# database.py

from sqlalchemy_helpers import Base, get_or_create, is_sqlite, exists_in_db
from sqlalchemy_helpers.flask_ext import DatabaseExtension, get_or_404, first_or_404

db = DatabaseExtension()
```

In the application factory, import the instance and call its `.init_app()` method:

```python
# app.py

from flask import Flask
from sqlalchemy_helpers.database import db

def create_app():
    """See https://flask.palletsprojects.com/en/1.1.x/patterns/appfactories/"""

    app = Flask(__name__)

    # Load the optional configuration file
    if "FLASK_CONFIG" in os.environ:
        app.config.from_envvar("FLASK_CONFIG")

    # Database
    db.init_app(app)

    return app
```

You can declare your models as you usually would with SQLAlchemy, just inherit
from the `Base` class that you re-exported in `database.py`:

```python
# models.py

from sqlalchemy import Column, Integer, Unicode

from .database import Base


class User(Base):

    __tablename__ = "users"

    id = Column("id", Integer, primary_key=True)
    name = Column(Unicode(254), index=True, unique=True, nullable=False)
    full_name = Column(Unicode(254), nullable=False)
    timezone = Column(Unicode(127), nullable=True)
```

In your views, you can use the instance's `session` property to access the
SQLAlchemy session object. There are also functions to ease classical view
patters such as getting an object by ID or returning a 404 error if not found.

```python
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
```

You can adjust alembic's `env.py` file to get the database URL from you app's
configuration:

```python
# migrations/env.py

from my_flask_app.app import create_app
from my_flask_app.database import Base
from sqlalchemy_helpers.flask_ext import get_url_from_app

url = get_url_from_app(create_app)
config.set_main_option("sqlalchemy.url", url)
target_metadata = Base.metadata

# ...rest of the env.py file...
```

Also set `script_location` in you alembic.ini file in order to use it with the
`alembic` command-line tool:

```python
# migrations/alembic.ini

[alembic]
script_location = %(here)s
```


### Full example

In Fedora Infrastructure we use [a cookiecutter
template](https://github.com/fedora-infra/cookiecutter-flask-webapp/) that
showcases this Flask integration, feel free to check it out or even use it if
it suits your needs.
