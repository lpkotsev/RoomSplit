import unittest
from decimal import Decimal

from roomsplit import create_app
from roomsplit.balances import calculate_room_balances
from roomsplit.splits import calculate_expense_shares


TEST_SECRET_KEY = "phase-seven-test-secret"


class PhaseSevenAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {"TESTING": True, "SECRET_KEY": TEST_SECRET_KEY}
        )
        self.storage = self.app.extensions["roomsplit_storage"]
        self.owner, self.owner_id = self.create_user("owner")
        created = self.owner.post(
            "/rooms/create",
            data={"name": "Shared event", "password": "room-password"},
        )
        self.assertEqual(created.status_code, 302)
        self.room = next(iter(self.storage.rooms.values()))

        self.administrator, self.administrator_id = self.create_user("admin")
        rejected_join = self.administrator.post(
            "/rooms/join",
            data={"room_code": self.room.code, "password": "wrong-password"},
        )
        self.assertEqual(rejected_join.status_code, 401)
        joined = self.administrator.post(
            "/rooms/join",
            data={"room_code": self.room.code, "password": "room-password"},
        )
        self.assertEqual(joined.status_code, 302)
        appointed = self.owner.post(
            f"/rooms/{self.room.id}/administrator",
            data={"member_id": self.administrator_id},
        )
        self.assertEqual(appointed.status_code, 302)
        self.assertEqual(self.room.administrator_id, self.administrator_id)

    def create_user(self, username):
        client = self.app.test_client()
        password = f"{username}-password"
        registered = client.post(
            "/register",
            data={"username": username, "password": password},
        )
        self.assertEqual(registered.status_code, 302)
        signed_in = client.post(
            "/sign-in",
            data={"username": username, "password": password},
        )
        self.assertEqual(signed_in.status_code, 302)
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
            if category.room_id == self.room.id and category.name == name
        )

    def create_expense(self, data):
        before = set(self.storage.expenses)
        response = self.owner.post(
            f"/rooms/{self.room.id}/expenses/new",
            data=data,
        )
        self.assertEqual(response.status_code, 302)
        return next(
            expense
            for expense_id, expense in self.storage.expenses.items()
            if expense_id not in before
        )

    def test_synthetic_journey_from_registration_through_dashboard(self):
        food = self.create_category("Food")
        travel = self.create_category("Travel")

        equal_expense = self.create_expense(
            {
                "item": "Shared meal",
                "amount": "10.00",
                "date": "2026-08-03",
                "category_id": food.id,
                "split_type": "equal",
                f"payer_{self.owner_id}": "10.00",
                "remainder_payer_id": self.owner_id,
            }
        )
        self.assertEqual(
            calculate_expense_shares(equal_expense),
            {
                self.owner_id: Decimal("5.00"),
                self.administrator_id: Decimal("5.00"),
            },
        )

        travel_expense = self.create_expense(
            {
                "item": "Train tickets",
                "amount": "6.00",
                "date": "2026-08-04",
                "category_id": travel.id,
                "split_type": "equal",
                f"payer_{self.owner_id}": "6.00",
            }
        )
        self.assertEqual(
            calculate_expense_shares(travel_expense),
            {
                self.owner_id: Decimal("3.00"),
                self.administrator_id: Decimal("3.00"),
            },
        )
        self.assertEqual(
            sum(calculate_expense_shares(travel_expense).values(), Decimal("0.00")),
            travel_expense.amount,
        )
        self.assertEqual(
            travel_expense.participant_ids,
            frozenset({self.owner_id, self.administrator_id}),
        )

        repayment = self.administrator.post(
            f"/rooms/{self.room.id}/repayments/new",
            data={
                "payer_id": self.administrator_id,
                "recipient_id": self.owner_id,
                "amount": "2.00",
                "date": "2026-08-06",
                "note": "Synthetic settlement",
            },
        )
        self.assertEqual(repayment.status_code, 302)
        balances = calculate_room_balances(
            self.storage.expenses.values(),
            member_ids=self.room.member_ids,
            repayments=self.storage.repayments.values(),
        )
        self.assertEqual(
            balances,
            {
                self.owner_id: Decimal("6.00"),
                self.administrator_id: Decimal("-6.00"),
            },
        )
        self.assertEqual(sum(balances.values(), Decimal("0.00")), Decimal("0.00"))

        dashboard = self.administrator.get(
            f"/rooms/{self.room.id}/dashboard"
            "?start_date=2026-08-03&end_date=2026-08-06"
        )
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn(b"Food", dashboard.data)
        self.assertIn(b"Travel", dashboard.data)
        self.assertIn(b"EUR 10.00", dashboard.data)
        self.assertIn(b"EUR 6.00", dashboard.data)
        self.assertIn(b"Owed EUR 6.00", dashboard.data)
        self.assertIn(b"Owes EUR 6.00", dashboard.data)

        expense_page = self.administrator.get(f"/rooms/{self.room.id}/expenses")
        self.assertEqual(expense_page.status_code, 200)
        self.assertIn(b"Shared meal", expense_page.data)
        self.assertIn(b"Train tickets", expense_page.data)
        repayment_page = self.administrator.get(f"/rooms/{self.room.id}/repayments")
        self.assertIn(b"Synthetic settlement", repayment_page.data)

        outsider, _ = self.create_user("outsider")
        protected_pages = (
            f"/rooms/{self.room.id}",
            f"/rooms/{self.room.id}/dashboard",
            f"/rooms/{self.room.id}/categories",
            f"/rooms/{self.room.id}/expenses/new",
            f"/rooms/{self.room.id}/repayments/new",
        )
        for path in protected_pages:
            with self.subTest(path=path):
                self.assertEqual(outsider.get(path).status_code, 403)

        protected_actions = (
            (f"/rooms/{self.room.id}/categories", {"name": "Private"}),
            (f"/rooms/{self.room.id}/expenses/new", {}),
            (f"/rooms/{self.room.id}/repayments/new", {}),
            (
                f"/rooms/{self.room.id}/administrator",
                {"member_id": outsider},
            ),
        )
        for path, data in protected_actions:
            with self.subTest(path=path):
                self.assertEqual(
                    outsider.post(path, data=data).status_code,
                    403,
                )

    def test_new_runtime_clears_records_and_invalidates_old_session(self):
        self.assertIn(self.owner_id, self.storage.accounts)
        cookie = self.owner.get_cookie(
            self.app.config["SESSION_COOKIE_NAME"]
        )

        fresh_app = create_app(
            {"TESTING": True, "SECRET_KEY": TEST_SECRET_KEY}
        )
        fresh_storage = fresh_app.extensions["roomsplit_storage"]
        self.assertEqual(fresh_storage.accounts, {})
        self.assertEqual(fresh_storage.rooms, {})
        self.assertEqual(fresh_storage.expenses, {})

        fresh_client = fresh_app.test_client()
        fresh_client.set_cookie(
            self.app.config["SESSION_COOKIE_NAME"],
            cookie.value,
        )
        response = fresh_client.get("/rooms")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/sign-in")
        with fresh_client.session_transaction() as user_session:
            self.assertEqual(dict(user_session), {})


if __name__ == "__main__":
    unittest.main()
