from .models import RoomRecord


def is_room_member(user_id: str, room: RoomRecord) -> bool:
    return user_id in room.member_ids


def is_room_manager(user_id: str, room: RoomRecord) -> bool:
    return is_room_member(user_id, room) and user_id in {
        room.owner_id,
        room.administrator_id,
    }


def has_privileged_room_role(user_id: str, room: RoomRecord) -> bool:
    return user_id in {room.owner_id, room.administrator_id}


def can_manage_record(user_id: str, room: RoomRecord, created_by: str) -> bool:
    return is_room_member(user_id, room) and (
        user_id == room.administrator_id or user_id == created_by
    )
