from flask import abort, current_app, g

from .models import RoomRecord
from .storage import RuntimeStorage


def get_storage() -> RuntimeStorage:
    return current_app.extensions["roomsplit_storage"]


def get_room_or_404(room_id: str) -> RoomRecord:
    room = get_storage().rooms.get(room_id)
    if room is None:
        abort(404)
    return room


def require_room_member(room: RoomRecord) -> None:
    if g.current_user.id not in room.member_ids:
        abort(403)
