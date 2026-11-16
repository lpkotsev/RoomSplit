import secrets

from flask import (
    Blueprint,
    abort,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from .auth import login_required
from .dashboard import _dashboard_rows
from .models import RoomRecord
from .permissions import (
    can_manage_record,
    has_privileged_room_role,
    is_room_manager,
    is_room_member,
)
from .security import hash_password, verify_password
from .room_access import get_room_or_404, get_storage, require_room_member


rooms_blueprint = Blueprint("rooms", __name__)


def _new_room_id() -> str:
    storage = get_storage()
    room_id = secrets.token_urlsafe(16)
    while room_id in storage.rooms:
        room_id = secrets.token_urlsafe(16)
    return room_id


def _new_room_code() -> str:
    storage = get_storage()
    code = secrets.token_urlsafe(8)
    while any(room.code == code for room in storage.rooms.values()):
        code = secrets.token_urlsafe(8)
    return code


def _new_invite_token() -> str:
    storage = get_storage()
    token = secrets.token_urlsafe(24)
    while any(room.invite_token == token for room in storage.rooms.values()):
        token = secrets.token_urlsafe(24)
    return token


def _render_room(room: RoomRecord, error=None, status=200, section=None):
    storage = get_storage()
    members = [
        storage.accounts[user_id]
        for user_id in room.member_ids
        if user_id in storage.accounts
    ]
    candidates = members
    categories = [
        category
        for category in storage.categories.values()
        if category.room_id == room.id
    ]
    expenses = [
        expense
        for expense in storage.expenses.values()
        if expense.room_id == room.id
    ]
    repayments = [
        repayment
        for repayment in storage.repayments.values()
        if repayment.room_id == room.id
    ]
    balance_rows = []
    has_balance_activity = False
    if section == "balances":
        _, balance_rows, _, has_balance_activity = _dashboard_rows(room, None, None)
    return (
        render_template(
            "room_detail.html",
            room=room,
            members=members,
            candidates=candidates,
            categories=categories,
            expenses=expenses,
            repayments=repayments,
            accounts=storage.accounts,
            error=error,
            invite_url=url_for(
                "rooms.join_by_invite",
                invite_token=room.invite_token,
            ),
            is_manager=is_room_manager(g.current_user.id, room),
            can_manage_record=can_manage_record,
            section=section,
            balance_rows=balance_rows,
            has_balance_activity=has_balance_activity,
        ),
        status,
    )


def _render_rooms(error=None, status=200, event_name=""):
    user_id = g.current_user.id
    rooms = [
        room
        for room in get_storage().rooms.values()
        if is_room_member(user_id, room)
    ]
    return render_template(
        "rooms.html", rooms=rooms, error=error, event_name=event_name
    ), status


def _find_room_by_code(code: str) -> RoomRecord | None:
    return next(
        (
            room
            for room in get_storage().rooms.values()
            if room.code == code
        ),
        None,
    )


def _find_room_by_invite(token: str) -> RoomRecord | None:
    return next(
        (
            room
            for room in get_storage().rooms.values()
            if room.invite_token == token
        ),
        None,
    )


@rooms_blueprint.get("/rooms")
@login_required
def index():
    return _render_rooms()


@rooms_blueprint.post("/rooms/create")
@login_required
def create():
    name = request.form.get("name", "").strip()
    if not name:
        return _render_rooms("Enter an event name.", 400)
    password = request.form.get("password", "")
    if not password:
        return _render_rooms("Enter an event password.", 400, name)

    owner_id = g.current_user.id
    room_id = _new_room_id()
    room = RoomRecord(
        id=room_id,
        name=name,
        code=_new_room_code(),
        invite_token=_new_invite_token(),
        password_hash=hash_password(password),
        owner_id=owner_id,
        member_ids={owner_id},
    )
    get_storage().rooms[room_id] = room
    return redirect(url_for("rooms.show", room_id=room_id))


@rooms_blueprint.route("/rooms/join", methods=["GET", "POST"])
@login_required
def join_by_code():
    if request.method == "GET":
        return _render_rooms()

    room_code = request.form.get("room_code", "")
    password = request.form.get("password", "")
    room = _find_room_by_code(room_code)
    if room is None or not password or not verify_password(
        room.password_hash,
        password,
    ):
        return _render_rooms("Invalid event hashcode or password.", 401)

    room.member_ids.add(g.current_user.id)
    return redirect(url_for("rooms.show", room_id=room.id))


@rooms_blueprint.route("/join/<invite_token>", methods=["GET", "POST"])
@login_required
def join_by_invite(invite_token: str):
    room = _find_room_by_invite(invite_token)
    if room is None:
        abort(404)

    if request.method == "GET":
        return render_template("join.html", room=room, error=None), 200

    password = request.form.get("password", "")
    if not password or not verify_password(room.password_hash, password):
        return (
            render_template(
                "join.html",
                room=room,
                error="Invalid event password.",
            ),
            401,
        )

    room.member_ids.add(g.current_user.id)
    return redirect(url_for("rooms.show", room_id=room.id))


@rooms_blueprint.get("/rooms/<room_id>")
@login_required
def show(room_id: str):
    room = get_room_or_404(room_id)
    require_room_member(room)
    return _render_room(room)


@rooms_blueprint.get("/rooms/<room_id>/<section>")
@login_required
def section(room_id: str, section: str):
    if section not in {"members", "expenses", "repayments", "balances"}:
        abort(404)
    room = get_room_or_404(room_id)
    require_room_member(room)
    return _render_room(room, section=section)


@rooms_blueprint.post("/rooms/<room_id>/administrator")
@login_required
def appoint_administrator(room_id: str):
    room = get_room_or_404(room_id)
    require_room_member(room)
    if g.current_user.id != room.owner_id:
        abort(403)
    if room.administrator_id is not None:
        return _render_room(room, "An administrator has already been appointed.", 409, "members")

    member_id = request.form.get("member_id", "")
    if (
        member_id not in room.member_ids
        or member_id not in get_storage().accounts
    ):
        return _render_room(
            room,
            "Choose a current event member.",
            400,
            "members",
        )

    room.administrator_id = member_id
    return redirect(url_for("rooms.section", room_id=room.id, section="members"))


@rooms_blueprint.post("/rooms/<room_id>/members/<member_id>/remove")
@login_required
def remove_member(room_id: str, member_id: str):
    room = get_room_or_404(room_id)
    require_room_member(room)
    if not is_room_manager(g.current_user.id, room):
        abort(403)
    if member_id not in room.member_ids:
        abort(404)
    if has_privileged_room_role(member_id, room):
        abort(403)

    room.member_ids.remove(member_id)
    return redirect(url_for("rooms.section", room_id=room.id, section="members"))


@rooms_blueprint.post("/rooms/<room_id>/leave")
@login_required
def leave(room_id: str):
    room = get_room_or_404(room_id)
    require_room_member(room)
    if has_privileged_room_role(g.current_user.id, room):
        abort(403)

    room.member_ids.remove(g.current_user.id)
    return redirect(url_for("rooms.index"))
