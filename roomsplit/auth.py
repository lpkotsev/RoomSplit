import secrets
from functools import wraps

from flask import (
    Blueprint,
    current_app,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from .models import AccountRecord
from .security import hash_password, verify_password
from .storage import RuntimeStorage


auth_blueprint = Blueprint("auth", __name__)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.current_user is None:
            return redirect(url_for("auth.sign_in"))
        return view(*args, **kwargs)

    return wrapped


def _storage() -> RuntimeStorage:
    return current_app.extensions["roomsplit_storage"]


def _new_account_id() -> str:
    storage = _storage()
    account_id = secrets.token_urlsafe(16)
    while account_id in storage.accounts:
        account_id = secrets.token_urlsafe(16)
    return account_id


@auth_blueprint.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    username = request.form.get("username", "")
    password = request.form.get("password", "")
    if not username.strip() or not password:
        return (
            render_template(
                "register.html",
                error="Enter a username and password.",
            ),
            400,
        )

    account_id = _new_account_id()
    _storage().accounts[account_id] = AccountRecord(
        id=account_id,
        username=username,
        password_hash=hash_password(password),
    )
    return redirect(url_for("auth.sign_in"))


@auth_blueprint.route("/sign-in", methods=["GET", "POST"])
def sign_in():
    if request.method == "GET":
        return render_template("sign_in.html")

    username = request.form.get("username", "")
    password = request.form.get("password", "")
    matches = [
        account
        for account in _storage().accounts.values()
        if account.username == username
        and verify_password(account.password_hash, password)
    ]
    if len(matches) != 1:
        return (
            render_template(
                "sign_in.html",
                error="Invalid username or password.",
            ),
            401,
        )

    session.clear()
    session["user_id"] = matches[0].id
    return redirect(url_for("rooms.index"))


@auth_blueprint.post("/sign-out")
def sign_out():
    session.clear()
    return redirect(url_for("auth.sign_in"))
