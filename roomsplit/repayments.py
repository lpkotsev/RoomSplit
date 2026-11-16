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
from .balances import repayment_capacity, validate_repayment_history
from .dates import parse_optional_date
from .models import RepaymentRecord, RoomRecord
from .money import parse_amount
from .permissions import can_manage_record
from .room_access import get_room_or_404, get_storage, require_room_member
from .splits import ZERO


repayments_blueprint = Blueprint("repayments", __name__)


def _new_id() -> str:
    storage = get_storage()
    repayment_id = secrets.token_urlsafe(16)
    while repayment_id in storage.repayments:
        repayment_id = secrets.token_urlsafe(16)
    return repayment_id


def _room_repayments(room_id: str) -> list[RepaymentRecord]:
    return [
        repayment
        for repayment in get_storage().repayments.values()
        if repayment.room_id == room_id
    ]


def _room_expenses(room_id: str):
    return [
        expense
        for expense in get_storage().expenses.values()
        if expense.room_id == room_id
    ]


def _render_form(
    room: RoomRecord,
    repayment: RepaymentRecord | None = None,
    error: str | None = None,
    status: int = 200,
    values: dict | None = None,
):
    member_ids = set(room.member_ids)
    if repayment is not None:
        member_ids.update({repayment.payer_id, repayment.recipient_id})
    members = sorted(
        (
            get_storage().accounts[member_id]
            for member_id in member_ids
            if member_id in get_storage().accounts
        ),
        key=lambda member: member.username,
    )
    if values is None:
        values = (
            {
                "payer_id": repayment.payer_id,
                "recipient_id": repayment.recipient_id,
                "amount": str(repayment.amount),
                "date": repayment.repayment_date.isoformat(),
                "note": repayment.note,
            }
            if repayment is not None
            else {}
        )
    return (
        render_template(
            "repayment_form.html",
            room=room,
            repayment=repayment,
            members=members,
            error=error,
            values=values,
        ),
        status,
    )


def _get_room_repayment(room_id: str, repayment_id: str) -> RepaymentRecord:
    repayment = get_storage().repayments.get(repayment_id)
    if repayment is None or repayment.room_id != room_id:
        abort(404)
    return repayment


def _parse_repayment(
    room: RoomRecord,
    repayment: RepaymentRecord | None = None,
) -> tuple[RepaymentRecord | None, str | None]:
    form = request.form
    payer_id = form.get("payer_id", "")
    recipient_id = form.get("recipient_id", "")
    allowed_member_ids = set(room.member_ids)
    if repayment is not None:
        allowed_member_ids.update({repayment.payer_id, repayment.recipient_id})
    if (
        payer_id not in allowed_member_ids
        or recipient_id not in allowed_member_ids
        or payer_id == recipient_id
    ):
        return None, "Choose two different members of this event."

    amount = parse_amount(form.get("amount", ""))
    if amount is None or amount <= ZERO:
        return None, "Enter a positive amount with no more than two decimal places."
    try:
        repayment_date = parse_optional_date(form.get("date", ""))
    except ValueError:
        return None, "Enter a valid repayment date."

    candidate = RepaymentRecord(
        id=repayment.id if repayment else _new_id(),
        room_id=room.id,
        payer_id=payer_id,
        recipient_id=recipient_id,
        amount=amount,
        repayment_date=repayment_date,
        note=form.get("note", "").strip(),
        created_by=repayment.created_by if repayment else g.current_user.id,
    )

    current_repayments = _room_repayments(room.id)
    if repayment is None:
        proposed = current_repayments + [candidate]
    else:
        proposed = [
            candidate if item.id == repayment.id else item
            for item in current_repayments
        ]
    ordered = [
        item
        for _, item in sorted(
            enumerate(proposed),
            key=lambda entry: (entry[1].repayment_date, entry[0]),
        )
    ]
    candidate_index = next(
        index
        for index, item in enumerate(ordered)
        if item.id == candidate.id
    )
    try:
        balances = validate_repayment_history(
            _room_expenses(room.id),
            room.member_ids,
            ordered[:candidate_index],
        )
    except ValueError:
        return None, "A recorded repayment exceeds the current balance between its members."

    if amount > repayment_capacity(balances, payer_id, recipient_id):
        return None, "Repayment exceeds the current balance between these members."

    try:
        validate_repayment_history(
            _room_expenses(room.id),
            room.member_ids,
            ordered,
        )
    except ValueError:
        return None, "This change would make a recorded repayment exceed the current balance."
    return candidate, None


@repayments_blueprint.route(
    "/rooms/<room_id>/repayments/new",
    methods=["GET", "POST"],
)
@login_required
def new_repayment(room_id: str):
    room = get_room_or_404(room_id)
    require_room_member(room)
    if request.method == "GET":
        return _render_form(room)

    repayment, error = _parse_repayment(room)
    if error:
        return _render_form(room, error=error, status=400, values=request.form)
    get_storage().repayments[repayment.id] = repayment
    return redirect(url_for("rooms.section", room_id=room.id, section="repayments"))


@repayments_blueprint.route(
    "/rooms/<room_id>/repayments/<repayment_id>/edit",
    methods=["GET", "POST"],
)
@login_required
def edit_repayment(room_id: str, repayment_id: str):
    room = get_room_or_404(room_id)
    require_room_member(room)
    repayment = _get_room_repayment(room_id, repayment_id)
    if not can_manage_record(g.current_user.id, room, repayment.created_by):
        abort(403)
    if request.method == "GET":
        return _render_form(room, repayment=repayment)

    updated, error = _parse_repayment(room, repayment)
    if error:
        return _render_form(
            room,
            repayment=repayment,
            error=error,
            status=400,
            values=request.form,
        )
    get_storage().repayments[repayment.id] = updated
    return redirect(url_for("rooms.section", room_id=room.id, section="repayments"))


@repayments_blueprint.post(
    "/rooms/<room_id>/repayments/<repayment_id>/delete"
)
@login_required
def delete_repayment(room_id: str, repayment_id: str):
    room = get_room_or_404(room_id)
    require_room_member(room)
    repayment = _get_room_repayment(room_id, repayment_id)
    if not can_manage_record(g.current_user.id, room, repayment.created_by):
        abort(403)
    remaining = [
        item
        for item in _room_repayments(room.id)
        if item.id != repayment.id
    ]
    try:
        validate_repayment_history(
            _room_expenses(room.id),
            room.member_ids,
            remaining,
        )
    except ValueError:
        return _render_form(
            room,
            repayment=repayment,
            error="Cannot delete this repayment because it would overpay a later repayment.",
            status=409,
        )
    del get_storage().repayments[repayment.id]
    return redirect(url_for("rooms.section", room_id=room.id, section="repayments"))
