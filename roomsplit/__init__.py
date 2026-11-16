import os

from flask import Flask, g, render_template, session
from dotenv import load_dotenv

from .auth import auth_blueprint
from .categories import categories_blueprint
from .dashboard import dashboard_blueprint
from .expenses import expenses_blueprint
from .models import AccountRecord
from .repayments import repayments_blueprint
from .rooms import rooms_blueprint
from .storage import RuntimeStorage


def create_app(test_config=None):
    load_dotenv()

    app = Flask(__name__)
    app.config.from_mapping(SECRET_KEY=os.environ.get("ROOMSPLIT_SECRET_KEY"))
    if test_config is not None:
        app.config.update(test_config)

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError(
            "Set ROOMSPLIT_SECRET_KEY in the environment or local .env file."
        )

    app.extensions["roomsplit_storage"] = RuntimeStorage()
    app.register_blueprint(auth_blueprint)
    app.register_blueprint(categories_blueprint)
    app.register_blueprint(dashboard_blueprint)
    app.register_blueprint(expenses_blueprint)
    app.register_blueprint(repayments_blueprint)
    app.register_blueprint(rooms_blueprint)

    @app.before_request
    def load_session_user():
        storage = app.extensions["roomsplit_storage"]
        user_id = session.get("user_id")
        account = (
            storage.accounts.get(user_id)
            if isinstance(user_id, str)
            else None
        )
        if user_id is not None and account is None:
            session.clear()
        elif account is not None and set(session.keys()) != {"user_id"}:
            session.clear()
            session["user_id"] = account.id
        g.current_user: AccountRecord | None = account

    @app.get("/")
    def index():
        return render_template("index.html")

    return app
