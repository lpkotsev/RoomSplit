import secrets
from decimal import Decimal

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
from .categories import category_suggestions, create_category, find_category_by_name
from .dates import parse_optional_date
from .models import ExpenseRecord, PayerContribution, RoomRecord
from .money import parse_amount
from .permissions import can_manage_record
from .room_access import get_room_or_404, get_storage, require_room_member


expenses_blueprint = Blueprint("expenses", __name__)


def _new_expense_id() -> str:
    storage = get_storage()
    expense_id = secrets.token_urlsafe(16)
    while expense_id in storage.expenses:
        expense_id = secrets.token_urlsafe(16)
    return expense_id


def _expense_form(
    room: RoomRecord, error=None, status=200, values=None, tied_payers=(),
    expense: ExpenseRecord | None = None,
):
    storage = get_storage()
    participant_ids = expense.participant_ids if expense else room.member_ids
    members = sorted(
        (
            storage.accounts[member_id]
            for member_id in participant_ids
            if member_id in storage.accounts
        ),
        key=lambda member: member.username,
    )
    if values is None:
        values = {}
        if expense is not None:
            category = storage.categories.get(expense.category_id)
            values = {
                "item": expense.item,
                "amount": str(expense.amount),
                "date": expense.expense_date.isoformat(),
                "category_name": category.name if category else "",
                "split_type": expense.split_type,
                "remainder_payer_id": expense.remainder_payer_id or "",
                **{f"payer_{payer.member_id}": str(payer.amount) for payer in expense.payers},
                **{f"share_{member_id}": str(share) for member_id, share in
                   (expense.custom_shares or {}).items()},
            }
    return (
        render_template(
            "expense_form.html",
            room=room,
            members=members,
            category_names=category_suggestions(room.id),
            error=error,
            values=values or {},
            tied_payers=tied_payers,
            expense=expense,
        ),
        status,
    )


def _invalid(room: RoomRecord, message: str, expense: ExpenseRecord | None = None):
    return _expense_form(room, message, 400, request.form, expense=expense)


def _get_room_expense(room_id: str, expense_id: str) -> ExpenseRecord:
    expense = get_storage().expenses.get(expense_id)
    if expense is None or expense.room_id != room_id:
        abort(404)
    return expense


def _history_valid(room: RoomRecord, expenses: list[ExpenseRecord]) -> bool:
    repayments = [
        repayment for repayment in get_storage().repayments.values()
        if repayment.room_id == room.id
    ]
    try:
        validate_repayment_history(expenses, room.member_ids, repayments)
    except ValueError:
        return False
    return True


def _room_expenses(room_id: str) -> list[ExpenseRecord]:
    return [
        expense for expense in get_storage().expenses.values()
        if expense.room_id == room_id
    ]


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
    return _save_expense(room)


def _save_expense(room: RoomRecord, expense: ExpenseRecord | None = None):
    def invalid(message: str):
        return _invalid(room, message, expense)

    item = request.form.get("item", "")
    if not item.strip():
        return invalid("Enter what the expense was for.")

    amount = parse_amount(request.form.get("amount", ""))
    if amount is None:
        return invalid(
            "Enter a valid amount with no more than two decimal places.",
        )
    if amount <= Decimal("0.00"):
        return invalid("Expense total must be greater than zero.")

    try:
        expense_date = parse_optional_date(request.form.get("date", ""))
    except ValueError:
        return invalid("Enter a valid expense date.")

    storage = get_storage()
    category_name = request.form.get("category_name")
    if category_name is not None:
        category_name = category_name.strip()
        if not category_name:
            return invalid("Enter a category.")
        category = find_category_by_name(room.id, category_name)
    else:
        category = storage.categories.get(request.form.get("category_id", ""))
        if category is None or category.room_id != room.id:
            return invalid("Choose a category for this event.")

    split_type = request.form.get("split_type", "equal")
    if split_type not in ("equal", "custom"):
        return invalid("Choose an equal or custom split.")

    participant_ids = expense.participant_ids if expense else frozenset(room.member_ids)
    payer_contributions = []
    for member_id in participant_ids:
        raw_amount = request.form.get(f"payer_{member_id}", "")
        if not raw_amount:
            continue
        payer_amount = parse_amount(raw_amount)
        if payer_amount is None:
            return invalid(
                "Enter valid payer amounts with no more than two decimal places.",
            )
        if payer_amount < Decimal("0.00"):
            return invalid("Payer contributions cannot be negative.")
        payer_contributions.append(
            PayerContribution(member_id=member_id, amount=payer_amount)
        )

    payer_total = sum(
        (payer.amount for payer in payer_contributions),
        Decimal("0.00"),
    )
    if not payer_contributions or payer_total != amount:
        return invalid(
            "Payer contributions must equal the expense total.",
        )

    custom_shares = None
    remainder_payer_id = None
    if split_type == "custom":
        custom_shares = {}
        for member_id in participant_ids:
            raw_share = request.form.get(f"share_{member_id}", "").strip()
            share = parse_amount(raw_share) if raw_share else Decimal("0.00")
            if share is None or share < Decimal("0.00"):
                return invalid("Enter non-negative custom shares with no more than two decimal places.")
            custom_shares[member_id] = share
        if sum(custom_shares.values(), Decimal("0.00")) != amount:
            return invalid("Custom shares must equal the expense total.")
    else:
        highest_amount = max(payer.amount for payer in payer_contributions)
        tied_ids = {
            payer.member_id for payer in payer_contributions
            if payer.amount == highest_amount
        }
        if len(tied_ids) == 1:
            remainder_payer_id = next(iter(tied_ids))
        else:
            remainder_payer_id = request.form.get("remainder_payer_id", "")
            if remainder_payer_id not in tied_ids:
                tied_payers = sorted(
                    (storage.accounts[member_id] for member_id in tied_ids),
                    key=lambda member: (member.username.casefold(), member.id),
                )
                return _expense_form(
                    room,
                    "Choose one of the highest payers to receive any rounding remainder.",
                    400,
                    request.form,
                    tied_payers,
                    expense,
                )

    candidate = ExpenseRecord(
        id=expense.id if expense else _new_expense_id(),
        room_id=room.id,
        item=item,
        amount=amount,
        expense_date=expense_date,
        category_id=category.id if category else "",
        split_type=split_type,
        payers=tuple(payer_contributions),
        participant_ids=participant_ids,
        custom_shares=custom_shares,
        created_by=expense.created_by if expense else g.current_user.id,
        remainder_payer_id=remainder_payer_id,
    )
    if expense is not None:
        proposed = [
            candidate if current.id == expense.id else current
            for current in _room_expenses(room.id)
        ]
        if not _history_valid(room, proposed):
            return _expense_form(
                room, "This change would make a recorded repayment exceed the current balance.",
                409, request.form, expense=expense,
            )
    if category is None:
        category = create_category(room.id, category_name, g.current_user.id)
        candidate.category_id = category.id
    storage.expenses[candidate.id] = candidate
    return redirect(url_for("rooms.section", room_id=room.id, section="expenses"))


@expenses_blueprint.route(
    "/rooms/<room_id>/expenses/<expense_id>/edit", methods=["GET", "POST"],
)
@login_required
def edit_expense(room_id: str, expense_id: str):
    room = get_room_or_404(room_id)
    require_room_member(room)
    expense = _get_room_expense(room_id, expense_id)
    if not can_manage_record(g.current_user.id, room, expense.created_by):
        abort(403)
    if request.method == "GET":
        return _expense_form(room, expense=expense)
    return _save_expense(room, expense)


@expenses_blueprint.post("/rooms/<room_id>/expenses/<expense_id>/delete")
@login_required
def delete_expense(room_id: str, expense_id: str):
    room = get_room_or_404(room_id)
    require_room_member(room)
    expense = _get_room_expense(room_id, expense_id)
    if not can_manage_record(g.current_user.id, room, expense.created_by):
        abort(403)
    remaining = [item for item in _room_expenses(room.id) if item.id != expense.id]
    if not _history_valid(room, remaining):
        return _expense_form(
            room, "Cannot delete this expense because it would overpay a recorded repayment.",
            409, expense=expense,
        )
    del get_storage().expenses[expense.id]
    return redirect(url_for("rooms.section", room_id=room.id, section="expenses"))
