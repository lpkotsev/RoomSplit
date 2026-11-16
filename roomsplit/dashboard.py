from datetime import date
from decimal import Decimal, ROUND_DOWN

from flask import Blueprint, render_template, request

from .auth import login_required
from .balances import calculate_room_balances
from .models import RoomRecord
from .room_access import get_room_or_404, get_storage, require_room_member
from .splits import ZERO


dashboard_blueprint = Blueprint("dashboard", __name__)


def _parse_date(value: str, label: str) -> date | None:
    if not value:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"Enter a valid {label}.") from None
    if parsed.isoformat() != value:
        raise ValueError(f"Enter a valid {label}.")
    return parsed


def _in_date_range(value: date, start: date | None, end: date | None) -> bool:
    return (start is None or value >= start) and (end is None or value <= end)


def _bar_width(value: Decimal, maximum: Decimal) -> int:
    if value == ZERO or maximum == ZERO:
        return 0
    percentage = int(
        (abs(value) * Decimal("100") / maximum).to_integral_value(
            rounding=ROUND_DOWN
        )
    )
    return max(1, min(100, percentage))


def _dashboard_rows(
    room: RoomRecord,
    start: date | None,
    end: date | None,
) -> tuple[list[dict], list[dict], bool, bool]:
    storage = get_storage()
    room_expenses = [
        expense
        for expense in storage.expenses.values()
        if expense.room_id == room.id
    ]
    expenses_in_range = [
        expense
        for expense in room_expenses
        if _in_date_range(expense.expense_date, start, end)
    ]
    category_totals: dict[str, Decimal] = {}
    categories_with_activity: set[str] = set()
    for expense in expenses_in_range:
        category_totals[expense.category_id] = (
            category_totals.get(expense.category_id, ZERO) + expense.amount
        )
        categories_with_activity.add(expense.category_id)

    categories = [
        category
        for category in storage.categories.values()
        if category.room_id == room.id
        and category.id in categories_with_activity
    ]
    max_category_total = max(
        (abs(category_totals[category.id]) for category in categories),
        default=ZERO,
    )
    category_rows = [
        {
            "name": category.name,
            "amount_display": (
                f"-EUR {abs(category_totals[category.id]):.2f}"
                if category_totals[category.id] < ZERO
                else f"EUR {category_totals[category.id]:.2f}"
            ),
            "bar_width": _bar_width(
                category_totals[category.id],
                max_category_total,
            ),
            "negative": category_totals[category.id] < ZERO,
        }
        for category in sorted(categories, key=lambda item: item.name.casefold())
    ]

    repayments_in_range = [
        repayment
        for repayment in storage.repayments.values()
        if repayment.room_id == room.id
        and _in_date_range(repayment.repayment_date, start, end)
    ]
    balances = calculate_room_balances(
        expenses_in_range,
        room.member_ids,
        repayments_in_range,
    )
    max_balance = max((abs(amount) for amount in balances.values()), default=ZERO)
    balance_rows = []
    for member_id, balance in balances.items():
        account = storage.accounts.get(member_id)
        is_current_member = member_id in room.member_ids
        if balance > ZERO:
            balance_label = "Owed"
        elif balance < ZERO:
            balance_label = "Owes"
        else:
            balance_label = "Balanced"
        balance_rows.append(
            {
                "name": account.username if account else "Former member",
                "is_current_member": is_current_member,
                "balance_label": balance_label,
                "amount_display": f"{abs(balance):.2f}",
                "bar_width": _bar_width(balance, max_balance),
                "negative": balance < ZERO,
            }
        )
    balance_rows.sort(
        key=lambda row: (not row["is_current_member"], row["name"].casefold())
    )
    return (
        category_rows,
        balance_rows,
        bool(categories_with_activity),
        bool(expenses_in_range or repayments_in_range),
    )


def _render_dashboard(
    room: RoomRecord,
    start_value: str,
    end_value: str,
    start: date | None,
    end: date | None,
    error: str | None = None,
    status: int = 200,
):
    if error:
        category_rows, balance_rows = [], []
        has_category_activity = False
        has_balance_activity = False
    else:
        (
            category_rows,
            balance_rows,
            has_category_activity,
            has_balance_activity,
        ) = _dashboard_rows(room, start, end)
    return (
        render_template(
            "dashboard.html",
            room=room,
            start_value=start_value,
            end_value=end_value,
            category_rows=category_rows,
            balance_rows=balance_rows,
            has_category_activity=has_category_activity,
            has_balance_activity=has_balance_activity,
            error=error,
        ),
        status,
    )


@dashboard_blueprint.get("/rooms/<room_id>/dashboard")
@login_required
def show(room_id: str):
    room = get_room_or_404(room_id)
    require_room_member(room)

    start_value = request.args.get("start_date", "")
    end_value = request.args.get("end_date", "")
    try:
        start = _parse_date(start_value, "start date")
        end = _parse_date(end_value, "end date")
        if start is not None and end is not None and start > end:
            raise ValueError("Start date must not be after end date.")
    except ValueError as error:
        return _render_dashboard(
            room,
            start_value,
            end_value,
            None,
            None,
            str(error),
            400,
        )

    return _render_dashboard(room, start_value, end_value, start, end)
