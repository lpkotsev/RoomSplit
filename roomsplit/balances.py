from collections.abc import Iterable
from decimal import Decimal, ROUND_DOWN

from .models import ExpenseRecord, RefundRecord, RepaymentRecord
from .money import CENT
from .splits import ZERO, calculate_expense_shares


def calculate_room_balances(
    expenses: Iterable[ExpenseRecord],
    member_ids: Iterable[str] = (),
    repayments: Iterable[RepaymentRecord] = (),
    refunds: Iterable[RefundRecord] = (),
) -> dict[str, Decimal]:
    """Return each member's net position: positive is owed, negative owes."""
    expense_records = tuple(expenses)
    repayment_records = tuple(repayments)
    refund_records = tuple(refunds)
    balances = _calculate_balances_before_repayments(
        expense_records,
        member_ids,
        refund_records,
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
    refunds: Iterable[RefundRecord],
    repayments: Iterable[RepaymentRecord],
) -> dict[str, Decimal]:
    balances = _calculate_balances_before_repayments(
        tuple(expenses),
        member_ids,
        tuple(refunds),
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
    refunds: Iterable[RefundRecord],
) -> dict[str, Decimal]:
    expense_records = tuple(expenses)
    refund_records = tuple(refunds)
    balances = {member_id: ZERO for member_id in member_ids}
    expense_by_id = {expense.id: expense for expense in expense_records}
    refunds_by_expense: dict[str, list[RefundRecord]] = {}
    for refund in refund_records:
        if refund.expense_id in expense_by_id:
            refunds_by_expense.setdefault(refund.expense_id, []).append(refund)

    for expense in expense_records:
        shares = calculate_expense_shares(expense)
        for member_id in shares:
            balances.setdefault(member_id, ZERO)
        for payer in expense.payers:
            balances.setdefault(payer.member_id, ZERO)
            balances[payer.member_id] += payer.amount
        for member_id, share in shares.items():
            balances[member_id] -= share

        linked_refunds = refunds_by_expense.get(expense.id, ())
        if not linked_refunds:
            continue
        total_refunded = sum(
            (refund.amount for refund in linked_refunds),
            ZERO,
        )
        if total_refunded > expense.amount:
            raise ValueError("Linked refunds exceed the original expense.")
        for refund in linked_refunds:
            for member_id, amount in (refund.payer_amounts or {}).items():
                balances.setdefault(member_id, ZERO)
                balances[member_id] -= amount
        share_reductions = _allocate_refund_shares(expense, total_refunded)
        for member_id, amount in share_reductions.items():
            balances[member_id] += amount
    return balances


def _allocate_refund_shares(
    expense: ExpenseRecord,
    refund_amount: Decimal,
) -> dict[str, Decimal]:
    shares = calculate_expense_shares(expense)
    if refund_amount == ZERO:
        return {member_id: ZERO for member_id in shares}

    allocations: dict[str, Decimal] = {}
    remainders: dict[str, Decimal] = {}
    for member_id, share in shares.items():
        exact_amount = refund_amount * share / expense.amount
        allocated = exact_amount.quantize(CENT, rounding=ROUND_DOWN)
        allocations[member_id] = allocated
        remainders[member_id] = exact_amount - allocated

    remaining = refund_amount - sum(allocations.values(), ZERO)
    remainder_payer_id = expense.remainder_payer_id
    order = sorted(
        shares,
        key=lambda member_id: (
            -remainders[member_id],
            member_id != remainder_payer_id,
            member_id,
        ),
    )
    for member_id in order:
        if remaining < CENT:
            break
        if allocations[member_id] + CENT <= shares[member_id]:
            allocations[member_id] += CENT
            remaining -= CENT
    if remaining != ZERO:
        raise ValueError("Refund shares cannot be reconciled to cents.")
    return allocations


def _apply_repayment(
    balances: dict[str, Decimal],
    repayment: RepaymentRecord,
) -> None:
    balances.setdefault(repayment.payer_id, ZERO)
    balances.setdefault(repayment.recipient_id, ZERO)
    balances[repayment.payer_id] += repayment.amount
    balances[repayment.recipient_id] -= repayment.amount
