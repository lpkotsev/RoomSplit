from collections.abc import Iterable
from decimal import Decimal

from .models import ExpenseRecord, RepaymentRecord
from .splits import ZERO, calculate_expense_shares


def calculate_room_balances(
    expenses: Iterable[ExpenseRecord],
    member_ids: Iterable[str] = (),
    repayments: Iterable[RepaymentRecord] = (),
) -> dict[str, Decimal]:
    """Return each member's net position: positive is owed, negative owes."""
    expense_records = tuple(expenses)
    repayment_records = tuple(repayments)
    balances = _calculate_balances_before_repayments(
        expense_records,
        member_ids,
    )
    for repayment in repayment_records:
        _apply_repayment(balances, repayment)
    return balances


def repayment_capacity(
    balances: dict[str, Decimal],
    payer_id: str,
    recipient_id: str,
) -> Decimal:
    payer_debt = max(-balances.get(payer_id, ZERO), ZERO)
    recipient_credit = max(balances.get(recipient_id, ZERO), ZERO)
    return min(payer_debt, recipient_credit)


def validate_repayment_history(
    expenses: Iterable[ExpenseRecord],
    member_ids: Iterable[str],
    repayments: Iterable[RepaymentRecord],
) -> dict[str, Decimal]:
    balances = _calculate_balances_before_repayments(
        tuple(expenses),
        member_ids,
    )
    for repayment in sorted(
        enumerate(repayments),
        key=lambda item: (item[1].repayment_date, item[0]),
    ):
        record = repayment[1]
        if record.amount <= ZERO or record.amount > repayment_capacity(
            balances,
            record.payer_id,
            record.recipient_id,
        ):
            raise ValueError(
                "A recorded repayment exceeds the current balance between its members."
            )
        _apply_repayment(balances, record)
    return balances


def _calculate_balances_before_repayments(
    expenses: Iterable[ExpenseRecord],
    member_ids: Iterable[str],
) -> dict[str, Decimal]:
    balances = {member_id: ZERO for member_id in member_ids}
    for expense in expenses:
        shares = calculate_expense_shares(expense)
        for member_id in shares:
            balances.setdefault(member_id, ZERO)
        for payer in expense.payers:
            balances.setdefault(payer.member_id, ZERO)
            balances[payer.member_id] += payer.amount
        for member_id, share in shares.items():
            balances[member_id] -= share

    return balances


def _apply_repayment(
    balances: dict[str, Decimal],
    repayment: RepaymentRecord,
) -> None:
    balances.setdefault(repayment.payer_id, ZERO)
    balances.setdefault(repayment.recipient_id, ZERO)
    balances[repayment.payer_id] += repayment.amount
    balances[repayment.recipient_id] -= repayment.amount
