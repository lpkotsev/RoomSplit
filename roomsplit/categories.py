import secrets

from flask import Blueprint, g, redirect, render_template, request, url_for

from .auth import login_required
from .models import CategoryRecord
from .room_access import get_room_or_404, get_storage, require_room_member


categories_blueprint = Blueprint("categories", __name__)


def _new_category_id() -> str:
    storage = get_storage()
    category_id = secrets.token_urlsafe(16)
    while category_id in storage.categories:
        category_id = secrets.token_urlsafe(16)
    return category_id


@categories_blueprint.route(
    "/rooms/<room_id>/categories",
    methods=["GET", "POST"],
)
@login_required
def index(room_id: str):
    room = get_room_or_404(room_id)
    require_room_member(room)
    storage = get_storage()
    categories = [
        category
        for category in storage.categories.values()
        if category.room_id == room.id
    ]

    if request.method == "GET":
        return render_template(
            "categories.html",
            room=room,
            categories=categories,
            error=None,
        )

    name = request.form.get("name", "")
    if not name.strip():
        return (
            render_template(
                "categories.html",
                room=room,
                categories=categories,
                error="Enter a category name.",
            ),
            400,
        )

    category_id = _new_category_id()
    storage.categories[category_id] = CategoryRecord(
        id=category_id,
        room_id=room.id,
        name=name,
        created_by=g.current_user.id,
    )
    return redirect(url_for("rooms.show", room_id=room.id))
