from datetime import date
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class AccountRecord:
    id: str
    username: str
    password_hash: str


@dataclass
class RoomRecord:
    id: str
    code: str
    invite_token: str
    password_hash: str
    owner_id: str
    member_ids: set[str] = field(default_factory=set)
    administrator_id: str | None = None


@dataclass
class CategoryRecord:
    id: str
    room_id: str
    name: str
    created_by: str


@dataclass
class PayerContribution:
    member_id: str
    amount: Decimal


@dataclass
class ExpenseRecord:
    id: str
    room_id: str
    item: str
    amount: Decimal
    expense_date: date
    category_id: str
    split_type: str
    payers: tuple[PayerContribution, ...]
    participant_ids: frozenset[str]
    custom_shares: dict[str, Decimal] | None
    created_by: str
    remainder_payer_id: str | None = None


@dataclass
class RepaymentRecord:
    id: str
    room_id: str
    payer_id: str
    recipient_id: str
    amount: Decimal
    repayment_date: date
    note: str
    created_by: str


@dataclass
class RefundRecord:
    id: str
    room_id: str
    amount: Decimal
    refund_date: date
    note: str
    expense_id: str | None
    payer_amounts: dict[str, Decimal] | None
    created_by: str
