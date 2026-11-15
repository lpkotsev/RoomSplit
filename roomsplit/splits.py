from decimal import Decimal, ROUND_DOWN

from .models import ExpenseRecord
from .money import CENT


ZERO = Decimal("0.00")


def calculate_expense_shares(expense: ExpenseRecord) -> dict[str, Decimal]:
    participants = sorted(expense.participant_ids)
    if not participants:
        raise ValueError("An expense must have at least one participant.")
    if (
        not isinstance(expense.amount, Decimal)
        or not expense.amount.is_finite()
        or expense.amount <= ZERO
        or expense.amount.quantize(CENT) != expense.amount
    ):
        raise ValueError("Expense total must be a positive cent amount.")

    payer_total = sum(
        (payer.amount for payer in expense.payers),
        ZERO,
    )
    if payer_total != expense.amount:
        raise ValueError("Payer contributions must equal the expense total.")

    if expense.split_type == "custom":
        if (
            expense.custom_shares is None
            or set(expense.custom_shares) != set(participants)
            or sum(expense.custom_shares.values(), ZERO) != expense.amount
        ):
            raise ValueError("Custom shares must equal the expense total.")
        return dict(expense.custom_shares)

    if expense.split_type != "equal":
        raise ValueError("Expense split type must be equal or custom.")

    payer_ids = {payer.member_id for payer in expense.payers}
    if (
        expense.remainder_payer_id not in participants
        or expense.remainder_payer_id not in payer_ids
    ):
        raise ValueError("Choose a recorded payer to receive the rounding remainder.")

    base_share = (expense.amount / Decimal(len(participants))).quantize(
        CENT,
        rounding=ROUND_DOWN,
    )
    shares = {member_id: base_share for member_id in participants}
    remainder = expense.amount - base_share * len(participants)
    shares[expense.remainder_payer_id] += remainder
    return shares
