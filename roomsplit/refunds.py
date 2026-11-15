import secrets
from datetime import date

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
from .balances import validate_repayment_history
from .models import RefundRecord, RoomRecord
from .money import parse_amount
from .room_access import get_room_or_404, get_storage, require_room_member
from .splits import ZERO


refunds_blueprint = Blueprint("refunds", __name__)


def _new_id() -> str:
    storage = get_storage()
    refund_id = secrets.token_urlsafe(16)
    while refund_id in storage.refunds:
        refund_id = secrets.token_urlsafe(16)
    return refund_id


def _room_expenses(room_id: str):
    return [
        expense
        for expense in get_storage().expenses.values()
        if expense.room_id == room_id
    ]


def _room_refunds(room_id: str) -> list[RefundRecord]:
    return [
        refund
        for refund in get_storage().refunds.values()
        if refund.room_id == room_id
    ]


def _room_repayments(room_id: str):
    return [
        repayment
        for repayment in get_storage().repayments.values()
        if repayment.room_id == room_id
    ]


def _render_form(
    room: RoomRecord,
    refund: RefundRecord | None = None,
    error: str | None = None,
    status: int = 200,
    values: dict | None = None,
):
    storage = get_storage()
    expenses = _room_expenses(room.id)
    payer_ids = {
        payer.member_id
        for expense in expenses
        for payer in expense.payers
    }
    payer_members = sorted(
        (
            storage.accounts[member_id]
            for member_id in payer_ids
            if member_id in storage.accounts
        ),
        key=lambda member: member.username,
    )
    if values is None:
        values = (
            {
                "expense_id": refund.expense_id or "",
                "amount": str(refund.amount),
                "date": refund.refund_date.isoformat(),
                "note": refund.note,
                **{
                    f"payer_{member_id}": str(amount)
                    for member_id, amount in (refund.payer_amounts or {}).items()
                },
            }
            if refund is not None
            else {}
        )
    return (
        render_template(
            "refund_form.html",
            room=room,
            refund=refund,
            expenses=expenses,
            payer_members=payer_members,
            error=error,
            values=values,
        ),
        status,
    )


def _get_room_refund(room_id: str, refund_id: str) -> RefundRecord:
    refund = get_storage().refunds.get(refund_id)
    if refund is None or refund.room_id != room_id:
        abort(404)
    return refund


def _parse_refund(
    room: RoomRecord,
    refund: RefundRecord | None = None,
) -> tuple[RefundRecord | None, str | None]:
    form = request.form
    amount = parse_amount(form.get("amount", ""))
    if amount is None or amount <= ZERO:
        return None, "Enter a positive amount with no more than two decimal places."
    try:
        refund_date = date.fromisoformat(form.get("date", ""))
    except ValueError:
        return None, "Enter a valid refund date."

    expense_id = form.get("expense_id", "") or None
    payer_amounts = None
    other_refunds = [
        item
        for item in _room_refunds(room.id)
        if refund is None or item.id != refund.id
    ]
    if expense_id is not None:
        expense = get_storage().expenses.get(expense_id)
        if expense is None or expense.room_id != room.id:
            return None, "Choose an expense from this room or leave it unlinked."

        linked_refunds = [
            item for item in other_refunds if item.expense_id == expense.id
        ]
        refunded_total = sum(
            (item.amount for item in linked_refunds),
            ZERO,
        )
        remaining_amount = expense.amount - refunded_total
        if amount > remaining_amount:
            return None, "Refund exceeds the remaining refundable amount."

        payer_amounts = {}
        for payer in expense.payers:
            raw_amount = form.get(f"payer_{payer.member_id}", "")
            payer_amount = parse_amount(raw_amount or "0")
            if payer_amount is None:
                return None, "Enter valid refund payer amounts with no more than two decimal places."
            if payer_amount < ZERO:
                return None, "Refund payer amounts cannot be negative."
            payer_amounts[payer.member_id] = payer_amount

        if sum(payer_amounts.values(), ZERO) != amount:
            return None, "Refund payer amounts must equal the refund total."

        for payer in expense.payers:
            already_refunded = sum(
                (
                    item.payer_amounts.get(payer.member_id, ZERO)
                    for item in linked_refunds
                ),
                ZERO,
            )
            if payer_amounts[payer.member_id] > payer.amount - already_refunded:
                return None, "Refund allocation exceeds that payer's remaining contribution."

    candidate = RefundRecord(
        id=refund.id if refund else _new_id(),
        room_id=room.id,
        amount=amount,
        refund_date=refund_date,
        note=form.get("note", "").strip(),
        expense_id=expense_id,
        payer_amounts=payer_amounts,
        created_by=refund.created_by if refund else g.current_user.id,
    )
    proposed_refunds = other_refunds + [candidate]
    try:
        validate_repayment_history(
            _room_expenses(room.id),
            room.member_ids,
            proposed_refunds,
            _room_repayments(room.id),
        )
    except ValueError:
        return None, "This change would make a recorded repayment exceed the current balance."
    return candidate, None


@refunds_blueprint.route(
    "/rooms/<room_id>/refunds/new",
    methods=["GET", "POST"],
)
@login_required
def new_refund(room_id: str):
    room = get_room_or_404(room_id)
    require_room_member(room)
    if request.method == "GET":
        return _render_form(room)

    refund, error = _parse_refund(room)
    if error:
        return _render_form(room, error=error, status=400, values=request.form)
    get_storage().refunds[refund.id] = refund
    return redirect(url_for("rooms.show", room_id=room.id))


@refunds_blueprint.route(
    "/rooms/<room_id>/refunds/<refund_id>/edit",
    methods=["GET", "POST"],
)
@login_required
def edit_refund(room_id: str, refund_id: str):
    room = get_room_or_404(room_id)
    require_room_member(room)
    refund = _get_room_refund(room_id, refund_id)
    if refund.created_by != g.current_user.id:
        abort(403)
    if request.method == "GET":
        return _render_form(room, refund=refund)

    updated, error = _parse_refund(room, refund)
    if error:
        return _render_form(
            room,
            refund=refund,
            error=error,
            status=400,
            values=request.form,
        )
    get_storage().refunds[refund.id] = updated
    return redirect(url_for("rooms.show", room_id=room.id))


@refunds_blueprint.post("/rooms/<room_id>/refunds/<refund_id>/delete")
@login_required
def delete_refund(room_id: str, refund_id: str):
    room = get_room_or_404(room_id)
    require_room_member(room)
    refund = _get_room_refund(room_id, refund_id)
    if refund.created_by != g.current_user.id:
        abort(403)
    remaining = [
        item for item in _room_refunds(room.id) if item.id != refund.id
    ]
    try:
        validate_repayment_history(
            _room_expenses(room.id),
            room.member_ids,
            remaining,
            _room_repayments(room.id),
        )
    except ValueError:
        return _render_form(
            room,
            refund=refund,
            error="Cannot delete this refund because it would overpay a recorded repayment.",
            status=409,
        )
    del get_storage().refunds[refund.id]
    return redirect(url_for("rooms.show", room_id=room.id))
