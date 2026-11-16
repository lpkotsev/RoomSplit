import unittest
from decimal import Decimal

from roomsplit import create_app
from roomsplit.balances import calculate_room_balances


class RepaymentSettlementTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SECRET_KEY": "settlement-test"})
        self.storage = self.app.extensions["roomsplit_storage"]
        self.owner, self.owner_id = self.create_user("owner")
        self.owner.post("/rooms/create", data={"name": "Event", "password": "event-password"})
        self.room = next(iter(self.storage.rooms.values()))
        self.member, self.member_id = self.create_user("member")
        self.member.post(
            "/rooms/join",
            data={"room_code": self.room.code, "password": "event-password"},
        )
        response = self.owner.post(
            f"/rooms/{self.room.id}/expenses/new",
            data={
                "item": "Dinner",
                "amount": "20.00",
                "date": "2026-01-01",
                "category_name": "Restaurant",
                f"payer_{self.owner_id}": "20.00",
            },
        )
        self.assertEqual(response.status_code, 302)

    def create_user(self, username):
        client = self.app.test_client()
        data = {"username": username, "password": "test-password"}
        self.assertEqual(client.post("/register", data=data).status_code, 302)
        self.assertEqual(client.post("/sign-in", data=data).status_code, 302)
        return client, next(
            account.id for account in self.storage.accounts.values()
            if account.username == username
        )

    def balances(self):
        return calculate_room_balances(
            self.storage.expenses.values(),
            self.room.member_ids,
            self.storage.repayments.values(),
        )

    def test_exact_repayment_settles_both_members_and_dashboard(self):
        self.assertEqual(self.balances()[self.member_id], Decimal("-10.00"))
        self.assertEqual(self.balances()[self.owner_id], Decimal("10.00"))
        response = self.member.post(
            f"/rooms/{self.room.id}/repayments/new",
            data={
                "payer_id": self.member_id,
                "recipient_id": self.owner_id,
                "amount": "10.00",
                "date": "2026-01-02",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.balances()[self.member_id], Decimal("0.00"))
        self.assertEqual(self.balances()[self.owner_id], Decimal("0.00"))
        dashboard = self.member.get(
            f"/rooms/{self.room.id}/dashboard?start_date=2026-01-01&end_date=2026-01-02"
        )
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn(b"member: Balanced EUR 0.00", dashboard.data)
        self.assertIn(b"owner: Balanced EUR 0.00", dashboard.data)
        self.assertIn(b"EUR 20.00", dashboard.data)
        expense_only = self.member.get(
            f"/rooms/{self.room.id}/dashboard?start_date=2026-01-01&end_date=2026-01-01"
        )
        self.assertIn(b"Owes EUR 10.00", expense_only.data)

    def test_refund_routes_and_storage_are_removed(self):
        self.assertFalse(hasattr(self.storage, "refunds"))
        for suffix in ("refunds/new", "refunds/fake/edit", "refunds/fake/delete"):
            path = f"/rooms/{self.room.id}/{suffix}"
            for method in (self.member.get, self.member.post):
                with self.subTest(path=path, method=method.__name__):
                    self.assertEqual(method(path).status_code, 404)
        page = self.member.get(f"/rooms/{self.room.id}")
        self.assertNotIn(b"Refund", page.data)

    def test_partial_repayment_changes_only_payer_and_recipient(self):
        third, third_id = self.create_user("third")
        third.post(
            "/rooms/join",
            data={"room_code": self.room.code, "password": "event-password"},
        )
        before = self.balances()
        response = third.post(
            f"/rooms/{self.room.id}/repayments/new",
            data={
                "payer_id": self.member_id,
                "recipient_id": self.owner_id,
                "amount": "4.00",
                "date": "2026-01-02",
            },
        )
        self.assertEqual(response.status_code, 302)
        after = self.balances()
        self.assertEqual(after[self.member_id] - before[self.member_id], Decimal("4.00"))
        self.assertEqual(after[self.owner_id] - before[self.owner_id], Decimal("-4.00"))
        self.assertEqual(after[third_id], before[third_id])
        self.assertEqual(sum(after.values(), Decimal("0.00")), Decimal("0.00"))


if __name__ == "__main__":
    unittest.main()
