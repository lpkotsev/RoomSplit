import unittest
from datetime import date
from decimal import Decimal

from roomsplit import create_app
from roomsplit.models import ExpenseRecord, PayerContribution
from roomsplit.splits import calculate_expense_shares
from roomsplit.balances import calculate_room_balances


TEST_SECRET_KEY = "phase-four-test-secret"


def make_expense(
    amount,
    participants,
    payers,
    *,
    split_type="equal",
    custom_shares=None,
    remainder_payer_id=None,
):
    return ExpenseRecord(
        id="expense",
        room_id="room",
        item="Shared item",
        amount=Decimal(amount),
        expense_date=date(2026, 8, 3),
        category_id="category",
        split_type=split_type,
        payers=tuple(
            PayerContribution(member_id, Decimal(value))
            for member_id, value in payers.items()
        ),
        participant_ids=frozenset(participants),
        custom_shares=custom_shares,
        created_by="recorder",
        remainder_payer_id=remainder_payer_id,
    )


class PhaseFourCalculationTests(unittest.TestCase):
    def test_equal_split_assigns_remainder_to_selected_payer(self):
        expense = make_expense(
            "10.00",
            ("alice", "bob", "carol"),
            {"alice": "10.00"},
            remainder_payer_id="alice",
        )

        shares = calculate_expense_shares(expense)

        self.assertEqual(
            shares,
            {
                "alice": Decimal("3.34"),
                "bob": Decimal("3.33"),
                "carol": Decimal("3.33"),
            },
        )
        self.assertEqual(sum(shares.values(), Decimal("0.00")), expense.amount)

    def test_base_down_rule_assigns_all_remainder_cents_to_selected_payer(self):
        expense = make_expense(
            "10.01",
            ("alice", "bob", "carol"),
            {"alice": "10.01"},
            remainder_payer_id="alice",
        )

        shares = calculate_expense_shares(expense)

        self.assertEqual(
            shares,
            {
                "alice": Decimal("3.35"),
                "bob": Decimal("3.33"),
                "carol": Decimal("3.33"),
            },
        )
        self.assertEqual(sum(shares.values(), Decimal("0.00")), expense.amount)

    def test_custom_shares_are_used_exactly_as_recorded(self):
        expense = make_expense(
            "10.00",
            ("alice", "bob", "carol"),
            {"alice": "5.00", "bob": "5.00"},
            split_type="custom",
            custom_shares={
                "alice": Decimal("2.25"),
                "bob": Decimal("7.75"),
                "carol": Decimal("0.00"),
            },
        )

        shares = calculate_expense_shares(expense)
        balances = calculate_room_balances([expense])

        self.assertEqual(shares, expense.custom_shares)
        self.assertEqual(sum(shares.values(), Decimal("0.00")), expense.amount)
        self.assertEqual(
            balances,
            {
                "alice": Decimal("2.75"),
                "bob": Decimal("-2.75"),
                "carol": Decimal("0.00"),
            },
        )

    def test_balances_include_all_payer_contributions_and_snapshotted_shares(self):
        expense = make_expense(
            "10.00",
            ("alice", "bob", "carol"),
            {"alice": "4.00", "bob": "6.00"},
            remainder_payer_id="alice",
        )

        balances = calculate_room_balances([expense])

        self.assertEqual(
            balances,
            {
                "alice": Decimal("0.66"),
                "bob": Decimal("2.67"),
                "carol": Decimal("-3.33"),
            },
        )
        self.assertEqual(sum(balances.values(), Decimal("0.00")), Decimal("0.00"))

    def test_membership_changes_do_not_change_expense_shares_or_balances(self):
        expense = make_expense(
            "10.00",
            ("alice", "bob", "carol"),
            {"alice": "10.00"},
            remainder_payer_id="alice",
        )

        balances = calculate_room_balances(
            [expense],
            member_ids={"alice", "bob", "dana"},
        )

        self.assertEqual(
            calculate_expense_shares(expense),
            {
                "alice": Decimal("3.34"),
                "bob": Decimal("3.33"),
                "carol": Decimal("3.33"),
            },
        )
        self.assertEqual(balances["carol"], Decimal("-3.33"))
        self.assertEqual(balances["dana"], Decimal("0.00"))
        self.assertEqual(sum(balances.values(), Decimal("0.00")), Decimal("0.00"))


class RemainderPayerEntryTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {"TESTING": True, "SECRET_KEY": TEST_SECRET_KEY}
        )
        self.storage = self.app.extensions["roomsplit_storage"]
        self.owner, self.owner_id = self.create_user("owner")
        self.owner.post("/rooms/create", data={"name": "Shared event", "password": "room-password"})
        self.room = next(iter(self.storage.rooms.values()))
        self.member, self.member_id = self.create_user("member")
        self.member.post(
            "/rooms/join",
            data={
                "room_code": self.room.code,
                "password": "room-password",
            },
        )
        self.owner.post(
            f"/rooms/{self.room.id}/categories",
            data={"name": "Shared costs"},
        )
        self.category = next(iter(self.storage.categories.values()))

    def create_user(self, username):
        client = self.app.test_client()
        password = f"{username}-password"
        self.assertEqual(
            client.post(
                "/register",
                data={"username": username, "password": password},
            ).status_code,
            302,
        )
        self.assertEqual(
            client.post(
                "/sign-in",
                data={"username": username, "password": password},
            ).status_code,
            302,
        )
        account = next(
            account
            for account in self.storage.accounts.values()
            if account.username == username
        )
        return client, account.id

    def expense_data(self, remainder_payer_id=""):
        return {
            "item": "Groceries",
            "amount": "10.00",
            "date": "2026-08-03",
            "category_id": self.category.id,
            "split_type": "equal",
            f"payer_{self.owner_id}": "4.00",
            f"payer_{self.member_id}": "6.00",
            "remainder_payer_id": remainder_payer_id,
        }

    def test_equal_expense_records_highest_payer_for_remainder(self):
        form = self.member.get(f"/rooms/{self.room.id}/expenses/new")
        self.assertEqual(form.status_code, 200)
        self.assertNotIn(b'name="remainder_payer_id"', form.data)

        response = self.member.post(
            f"/rooms/{self.room.id}/expenses/new",
            data=self.expense_data(self.owner_id),
        )

        self.assertEqual(response.status_code, 302)
        expense = next(iter(self.storage.expenses.values()))
        self.assertEqual(expense.remainder_payer_id, self.member_id)

    def test_single_highest_payer_does_not_require_selection(self):
        response = self.member.post(
            f"/rooms/{self.room.id}/expenses/new",
            data=self.expense_data(),
        )
        self.assertEqual(response.status_code, 302)
        expense = next(iter(self.storage.expenses.values()))
        self.assertEqual(expense.remainder_payer_id, self.member_id)


if __name__ == "__main__":
    unittest.main()
