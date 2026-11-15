import unittest
from datetime import date
from decimal import Decimal

from roomsplit import create_app
from roomsplit.models import RefundRecord, RepaymentRecord


TEST_SECRET_KEY = "phase-six-test-secret"


class PhaseSixDashboardTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {"TESTING": True, "SECRET_KEY": TEST_SECRET_KEY}
        )
        self.storage = self.app.extensions["roomsplit_storage"]
        self.owner, self.owner_id = self.create_user("owner")
        self.owner.post("/rooms/create", data={"password": "room-password"})
        self.room = next(iter(self.storage.rooms.values()))
        self.member, self.member_id = self.create_user("member")
        self.member.post(
            "/rooms/join",
            data={
                "room_code": self.room.code,
                "password": "room-password",
            },
        )
        self.food = self.create_category("Food")
        self.travel = self.create_category("Travel")

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

    def create_category(self, name):
        response = self.owner.post(
            f"/rooms/{self.room.id}/categories",
            data={"name": name},
        )
        self.assertEqual(response.status_code, 302)
        return next(
            category
            for category in self.storage.categories.values()
            if category.name == name
        )

    def create_expense(self, category, amount, expense_date):
        response = self.owner.post(
            f"/rooms/{self.room.id}/expenses/new",
            data={
                "item": f"{category.name} expense",
                "amount": amount,
                "date": expense_date,
                "category_id": category.id,
                "split_type": "equal",
                f"payer_{self.owner_id}": amount,
                "remainder_payer_id": self.owner_id,
            },
        )
        self.assertEqual(response.status_code, 302)
        return max(
            self.storage.expenses.values(),
            key=lambda expense: expense.expense_date,
        )

    def add_linked_refund(self, expense, amount, refund_date, payer_id=None):
        refund = RefundRecord(
            id=f"refund-{len(self.storage.refunds)}",
            room_id=self.room.id,
            amount=Decimal(amount),
            refund_date=date.fromisoformat(refund_date),
            note="synthetic test refund",
            expense_id=expense.id,
            payer_amounts={payer_id or self.owner_id: Decimal(amount)},
            created_by=self.member_id,
        )
        self.storage.refunds[refund.id] = refund
        return refund

    def test_inclusive_date_filter_aggregates_category_and_filtered_balances(self):
        first = self.create_expense(self.food, "10.00", "2026-01-01")
        self.create_expense(self.food, "5.00", "2026-01-10")
        self.create_expense(self.travel, "3.00", "2025-12-31")
        self.add_linked_refund(first, "2.00", "2026-01-10")
        self.storage.refunds["unlinked"] = RefundRecord(
            id="unlinked",
            room_id=self.room.id,
            amount=Decimal("9.00"),
            refund_date=date(2026, 1, 5),
            note="synthetic unlinked refund",
            expense_id=None,
            payer_amounts=None,
            created_by=self.member_id,
        )
        self.storage.repayments["repayment"] = RepaymentRecord(
            id="repayment",
            room_id=self.room.id,
            payer_id=self.member_id,
            recipient_id=self.owner_id,
            amount=Decimal("1.00"),
            repayment_date=date(2026, 1, 10),
            note="synthetic repayment",
            created_by=self.member_id,
        )

        response = self.member.get(
            f"/rooms/{self.room.id}/dashboard"
            "?start_date=2026-01-01&end_date=2026-01-10"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"EUR 13.00", response.data)
        self.assertIn(b"EUR 5.50", response.data)
        self.assertIn(b"Food", response.data)
        self.assertNotIn(b"Travel", response.data)
        self.assertNotIn(b"EUR 9.00", response.data)
        self.assertIn(b"type=\"date\"", response.data)

    def test_linked_refund_in_range_can_reduce_category_of_out_of_range_expense(self):
        expense = self.create_expense(self.food, "10.00", "2025-12-31")
        self.add_linked_refund(expense, "2.00", "2026-01-01")

        response = self.member.get(
            f"/rooms/{self.room.id}/dashboard"
            "?start_date=2026-01-01&end_date=2026-01-01"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Food", response.data)
        self.assertIn(b"-EUR 2.00", response.data)
        self.assertIn(b"No balance activity in this date range.", response.data)

    def test_empty_range_shows_clear_empty_states_and_zero_member_balances(self):
        self.create_expense(self.food, "10.00", "2026-01-01")

        response = self.member.get(
            f"/rooms/{self.room.id}/dashboard"
            "?start_date=2026-02-01&end_date=2026-02-28"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No spending recorded in this date range.", response.data)
        self.assertIn(b"No balance activity in this date range.", response.data)
        self.assertIn(b"owner", response.data)
        self.assertIn(b"member", response.data)
        self.assertIn(b"EUR 0.00", response.data)

    def test_date_range_validation_and_unbounded_default(self):
        invalid = self.member.get(
            f"/rooms/{self.room.id}/dashboard"
            "?start_date=2026-02-01&end_date=2026-01-01"
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertIn(b"Start date must not be after end date.", invalid.data)

        all_time = self.member.get(f"/rooms/{self.room.id}/dashboard")
        self.assertEqual(all_time.status_code, 200)
        self.assertIn(b"Showing all dates.", all_time.data)

    def test_nonmember_cannot_view_dashboard_or_filtered_room_data(self):
        outsider, _ = self.create_user("outsider")

        response = outsider.get(
            f"/rooms/{self.room.id}/dashboard"
            "?start_date=2026-01-01&end_date=2026-01-31"
        )

        self.assertEqual(response.status_code, 403)

    def test_room_detail_links_to_dashboard(self):
        response = self.member.get(f"/rooms/{self.room.id}")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            f'href="/rooms/{self.room.id}/dashboard"'.encode(),
            response.data,
        )


if __name__ == "__main__":
    unittest.main()
