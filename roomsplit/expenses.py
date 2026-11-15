import secrets
from datetime import date
from decimal import Decimal

from flask import (
    Blueprint,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from .auth import login_required
from .models import ExpenseRecord, PayerContribution, RoomRecord
from .money import parse_amount
from .room_access import get_room_or_404, get_storage, require_room_member


expenses_blueprint = Blueprint("expenses", __name__)


def _new_expense_id() -> str:
    storage = get_storage()
    expense_id = secrets.token_urlsafe(16)
    while expense_id in storage.expenses:
        expense_id = secrets.token_urlsafe(16)
    return expense_id


def _expense_form(room: RoomRecord, error=None, status=200, values=None):
    storage = get_storage()
    members = sorted(
        (
            storage.accounts[member_id]
            for member_id in room.member_ids
            if member_id in storage.accounts
        ),
        key=lambda member: member.username,
    )
    categories = [
        category
        for category in storage.categories.values()
        if category.room_id == room.id
    ]
    return (
        render_template(
            "expense_form.html",
            room=room,
            members=members,
            categories=categories,
            error=error,
            values=values or {},
        ),
        status,
    )


def _invalid(room: RoomRecord, message: str):
    return _expense_form(room, message, 400, request.form)


@expenses_blueprint.route(
    "/rooms/<room_id>/expenses/new",
    methods=["GET", "POST"],
)
@login_required
def new_expense(room_id: str):
    room = get_room_or_404(room_id)
    require_room_member(room)
    if request.method == "GET":
        return _expense_form(room)

    item = request.form.get("item", "")
    if not item.strip():
        return _invalid(room, "Enter what the expense was for.")

    amount = parse_amount(request.form.get("amount", ""))
    if amount is None:
        return _invalid(
            room,
            "Enter a valid amount with no more than two decimal places.",
        )
    if amount <= Decimal("0.00"):
        return _invalid(room, "Expense total must be greater than zero.")

    try:
        expense_date = date.fromisoformat(request.form.get("date", ""))
    except ValueError:
        return _invalid(room, "Enter a valid expense date.")

    storage = get_storage()
    category_id = request.form.get("category_id", "")
    category = storage.categories.get(category_id)
    if category is None or category.room_id != room.id:
        return _invalid(room, "Choose a category for this room.")

    split_type = request.form.get("split_type", "")
    if split_type not in {"equal", "custom"}:
        return _invalid(room, "Choose an equal or custom split.")

    payer_contributions = []
    for member_id in room.member_ids:
        raw_amount = request.form.get(f"payer_{member_id}", "")
        if not raw_amount:
            continue
        payer_amount = parse_amount(raw_amount)
        if payer_amount is None:
            return _invalid(
                room,
                "Enter valid payer amounts with no more than two decimal places.",
            )
        if payer_amount < Decimal("0.00"):
            return _invalid(room, "Payer contributions cannot be negative.")
        payer_contributions.append(
            PayerContribution(member_id=member_id, amount=payer_amount)
        )

    payer_total = sum(
        (payer.amount for payer in payer_contributions),
        Decimal("0.00"),
    )
    if not payer_contributions or payer_total != amount:
        return _invalid(
            room,
            "Payer contributions must equal the expense total.",
        )

    remainder_payer_id = None
    if split_type == "equal":
        remainder_payer_id = request.form.get("remainder_payer_id", "")
        if remainder_payer_id not in {
            payer.member_id for payer in payer_contributions
        }:
            return _invalid(
                room,
                "Choose a payer to receive any rounding remainder.",
            )

    custom_shares = None
    if split_type == "custom":
        custom_shares = {}
        for member_id in room.member_ids:
            raw_share = request.form.get(f"share_{member_id}", "")
            if not raw_share:
                return _invalid(
                    room,
                    "Enter a custom share for every room member.",
                )
            share = parse_amount(raw_share)
            if share is None:
                return _invalid(
                    room,
                    "Enter valid custom shares with no more than two decimal places.",
                )
            if share < Decimal("0.00"):
                return _invalid(room, "Custom shares cannot be negative.")
            custom_shares[member_id] = share

        custom_total = sum(custom_shares.values(), Decimal("0.00"))
        if custom_total != amount:
            return _invalid(
                room,
                "Custom shares must equal the expense total.",
            )

    expense_id = _new_expense_id()
    storage.expenses[expense_id] = ExpenseRecord(
        id=expense_id,
        room_id=room.id,
        item=item,
        amount=amount,
        expense_date=expense_date,
        category_id=category.id,
        split_type=split_type,
        payers=tuple(payer_contributions),
        participant_ids=frozenset(room.member_ids),
        custom_shares=custom_shares,
        created_by=g.current_user.id,
        remainder_payer_id=remainder_payer_id,
    )
    return redirect(url_for("rooms.show", room_id=room.id))
