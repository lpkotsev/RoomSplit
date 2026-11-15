from dataclasses import dataclass, field

from .models import (
    AccountRecord,
    CategoryRecord,
    ExpenseRecord,
    RefundRecord,
    RepaymentRecord,
    RoomRecord,
)


@dataclass
class RuntimeStorage:
    accounts: dict[str, AccountRecord] = field(default_factory=dict)
    rooms: dict[str, RoomRecord] = field(default_factory=dict)
    categories: dict[str, CategoryRecord] = field(default_factory=dict)
    expenses: dict[str, ExpenseRecord] = field(default_factory=dict)
    repayments: dict[str, RepaymentRecord] = field(default_factory=dict)
    refunds: dict[str, RefundRecord] = field(default_factory=dict)
