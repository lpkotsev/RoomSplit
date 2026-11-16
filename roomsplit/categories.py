import secrets

from flask import Blueprint, g, redirect, render_template, request, url_for

from .auth import login_required
from .models import CategoryRecord
from .room_access import get_room_or_404, get_storage, require_room_member


categories_blueprint = Blueprint("categories", __name__)

DEFAULT_CATEGORY_NAMES = (
    "Restaurant",
    "Entertainment",
    "Groceries",
    "Transport",
    "Accommodation",
    "Utilities",
)


def category_suggestions(room_id: str) -> list[str]:
    names = {name.casefold(): name for name in DEFAULT_CATEGORY_NAMES}
    for category in get_storage().categories.values():
        if category.room_id == room_id:
            names[category.name.strip().casefold()] = category.name
    return sorted(names.values(), key=str.casefold)


def find_category_by_name(room_id: str, name: str) -> CategoryRecord | None:
    key = name.strip().casefold()
    return next(
        (
            category
            for category in get_storage().categories.values()
            if category.room_id == room_id
            and category.name.strip().casefold() == key
        ),
        None,
    )


def create_category(room_id: str, name: str, created_by: str) -> CategoryRecord:
    canonical_name = next(
        (default for default in DEFAULT_CATEGORY_NAMES if default.casefold() == name.casefold()),
        name,
    )
    category = CategoryRecord(
        id=_new_category_id(),
        room_id=room_id,
        name=canonical_name,
        created_by=created_by,
    )
    get_storage().categories[category.id] = category
    return category


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

    if find_category_by_name(room.id, name) is None:
        create_category(room.id, name.strip(), g.current_user.id)
    return redirect(url_for("rooms.show", room_id=room.id))
