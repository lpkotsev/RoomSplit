import unittest
from datetime import date
from decimal import Decimal

from roomsplit import create_app


TEST_SECRET_KEY = "phase-three-test-secret"


class PhaseThreeTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {"TESTING": True, "SECRET_KEY": TEST_SECRET_KEY}
        )
        self.storage = self.app.extensions["roomsplit_storage"]
        self.owner, self.owner_id = self.create_user("owner")
        response = self.owner.post(
            "/rooms/create",
            data={"password": "room-password"},
        )
        self.assertEqual(response.status_code, 302)
        self.room = next(iter(self.storage.rooms.values()))

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

    def add_member(self, username):
        client, member_id = self.create_user(username)
        response = client.post(
            "/rooms/join",
            data={
                "room_code": self.room.code,
                "password": "room-password",
            },
        )
        self.assertEqual(response.status_code, 302)
        return client, member_id

    def create_category(self, client, name="Shared costs"):
        response = client.post(
            f"/rooms/{self.room.id}/categories",
            data={"name": name},
        )
        self.assertEqual(response.status_code, 302)
        return next(
            category
            for category in self.storage.categories.values()
            if category.room_id == self.room.id and category.name == name
        )

    def expense_data(self, category, amount="10.00", split_type="equal"):
        data = {
            "item": "Groceries",
            "amount": amount,
            "date": "2026-08-03",
            "category_id": category.id,
            "split_type": split_type,
            f"payer_{self.owner_id}": amount,
        }
        if split_type == "equal":
            data["remainder_payer_id"] = self.owner_id
        return data

    def create_expense(self, client, category, data=None):
        stored_ids = set(self.storage.expenses)
        response = client.post(
            f"/rooms/{self.room.id}/expenses/new",
            data=data or self.expense_data(category),
        )
        self.assertEqual(response.status_code, 302)
        return next(
            expense
            for expense_id, expense in self.storage.expenses.items()
            if expense_id not in stored_ids
        )

    def test_equal_expense_records_decimal_values_and_member_snapshot(self):
        member, member_id = self.add_member("member")
        category = self.create_category(self.owner)
        expense_form = self.owner.get(
            f"/rooms/{self.room.id}/expenses/new"
        )
        self.assertEqual(expense_form.status_code, 200)
        data = self.expense_data(category)
        data[f"payer_{self.owner_id}"] = "4.00"
        data[f"payer_{member_id}"] = "6.00"

        expense = self.create_expense(member, category, data)

        self.assertEqual(expense.amount, Decimal("10.00"))
        self.assertEqual(expense.amount.as_tuple().exponent, -2)
        self.assertEqual(expense.expense_date, date(2026, 8, 3))
        self.assertEqual(expense.split_type, "equal")
        self.assertIsNone(expense.custom_shares)
        self.assertEqual(expense.participant_ids, {self.owner_id, member_id})
        self.assertTrue(
            all(payer.amount.as_tuple().exponent == -2 for payer in expense.payers)
        )
        self.assertEqual(
            {payer.member_id: payer.amount for payer in expense.payers},
            {
                self.owner_id: Decimal("4.00"),
                member_id: Decimal("6.00"),
            },
        )
        room_page = self.owner.get(f"/rooms/{self.room.id}")
        self.assertEqual(room_page.status_code, 200)
        self.assertIn(b"Groceries", room_page.data)

        later_member, later_member_id = self.add_member("later")
        self.assertIn(later_member_id, self.room.member_ids)
        self.assertEqual(
            expense.participant_ids,
            frozenset({self.owner_id, member_id}),
        )

        member.post(f"/rooms/{self.room.id}/leave")
        self.assertNotIn(member_id, self.room.member_ids)
        self.assertEqual(
            expense.participant_ids,
            frozenset({self.owner_id, member_id}),
        )

    def test_custom_expense_requires_each_member_share_and_records_no_calculation(self):
        member, member_id = self.add_member("member")
        category = self.create_category(self.owner)
        data = self.expense_data(category, split_type="custom")
        data[f"payer_{self.owner_id}"] = "5.00"
        data[f"payer_{member_id}"] = "5.00"
        data[f"share_{self.owner_id}"] = "2.25"
        data[f"share_{member_id}"] = "7.75"

        negative_share_data = {
            **data,
            f"share_{self.owner_id}": "11.00",
            f"share_{member_id}": "-1.00",
        }
        negative_share = member.post(
            f"/rooms/{self.room.id}/expenses/new",
            data=negative_share_data,
        )
        self.assertEqual(negative_share.status_code, 400)
        self.assertIn(b"Custom shares cannot be negative.", negative_share.data)
        self.assertEqual(self.storage.expenses, {})

        expense = self.create_expense(member, category, data)

        self.assertEqual(expense.split_type, "custom")
        self.assertEqual(
            expense.custom_shares,
            {
                self.owner_id: Decimal("2.25"),
                member_id: Decimal("7.75"),
            },
        )
        self.assertEqual(
            sum(expense.custom_shares.values(), Decimal("0.00")),
            expense.amount,
        )
        zero_share_data = self.expense_data(category, split_type="custom")
        zero_share_data[f"share_{self.owner_id}"] = "10.00"
        zero_share_data[f"share_{member_id}"] = "0.00"
        zero_share_expense = self.create_expense(
            member,
            category,
            zero_share_data,
        )
        self.assertEqual(
            zero_share_expense.custom_shares[member_id],
            Decimal("0.00"),
        )

    def test_member_can_create_category_and_nonmember_cannot(self):
        member, _ = self.add_member("member")

        response = member.post(
            f"/rooms/{self.room.id}/categories",
            data={"name": "Transport"},
        )

        self.assertEqual(response.status_code, 302)
        category = next(iter(self.storage.categories.values()))
        self.assertEqual(category.name, "Transport")
        self.assertEqual(category.room_id, self.room.id)
        self.assertEqual(
            member.get(f"/rooms/{self.room.id}/categories").status_code,
            200,
        )

        outsider, _ = self.create_user("outsider")
        denied = outsider.post(
            f"/rooms/{self.room.id}/categories",
            data={"name": "Private"},
        )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(len(self.storage.categories), 1)

    def test_nonmember_cannot_read_or_create_room_expenses(self):
        outsider, _ = self.create_user("outsider")
        category = self.create_category(self.owner)

        page = outsider.get(f"/rooms/{self.room.id}/expenses/new")
        response = outsider.post(
            f"/rooms/{self.room.id}/expenses/new",
            data=self.expense_data(category),
        )

        self.assertEqual(page.status_code, 403)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.storage.expenses, {})

    def test_invalid_expenses_are_rejected_without_storage(self):
        category = self.create_category(self.owner)
        valid = self.expense_data(category)
        cases = [
            (
                {**valid, "amount": "1.001"},
                "Enter a valid amount with no more than two decimal places.",
            ),
            (
                {**valid, "amount": "NaN"},
                "Enter a valid amount with no more than two decimal places.",
            ),
            (
                {**valid, "amount": "0.00"},
                "Expense total must be greater than zero.",
            ),
            (
                {**valid, f"payer_{self.owner_id}": "9.99"},
                "Payer contributions must equal the expense total.",
            ),
            (
                {**valid, f"payer_{self.owner_id}": "10.001"},
                "Enter valid payer amounts with no more than two decimal places.",
            ),
            (
                {**valid, f"payer_{self.owner_id}": "-10.00"},
                "Payer contributions cannot be negative.",
            ),
            (
                {**valid, "date": "not-a-date"},
                "Enter a valid expense date.",
            ),
            (
                {**valid, "category_id": "unknown"},
                "Choose a category for this room.",
            ),
            (
                {**valid, "split_type": "unknown"},
                "Choose an equal or custom split.",
            ),
            (
                {**valid, "item": "  "},
                "Enter what the expense was for.",
            ),
        ]

        for data, error in cases:
            with self.subTest(data=data):
                response = self.owner.post(
                    f"/rooms/{self.room.id}/expenses/new",
                    data=data,
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn(error.encode(), response.data)
                self.assertEqual(self.storage.expenses, {})

    def test_custom_split_must_cover_every_member_and_match_the_total(self):
        member, member_id = self.add_member("member")
        category = self.create_category(self.owner)
        data = self.expense_data(category, split_type="custom")
        data[f"share_{self.owner_id}"] = "10.00"

        missing_share = member.post(
            f"/rooms/{self.room.id}/expenses/new",
            data=data,
        )
        self.assertEqual(missing_share.status_code, 400)
        self.assertIn(b"Enter a custom share for every room member.", missing_share.data)

        data[f"share_{member_id}"] = "1.00"
        data[f"payer_{self.owner_id}"] = "10.00"
        mismatch = member.post(
            f"/rooms/{self.room.id}/expenses/new",
            data=data,
        )
        self.assertEqual(mismatch.status_code, 400)
        self.assertIn(b"Custom shares must equal the expense total.", mismatch.data)
        self.assertEqual(self.storage.expenses, {})

    def test_expense_requires_payer_and_categories_are_room_scoped(self):
        category = self.create_category(self.owner)
        data = self.expense_data(category)
        data.pop(f"payer_{self.owner_id}")

        no_payer = self.owner.post(
            f"/rooms/{self.room.id}/expenses/new",
            data=data,
        )
        self.assertEqual(no_payer.status_code, 400)
        self.assertIn(b"Payer contributions must equal the expense total.", no_payer.data)

        other_client, _ = self.create_user("other")
        other_room_response = other_client.post(
            "/rooms/create",
            data={"password": "other-room-password"},
        )
        self.assertEqual(other_room_response.status_code, 302)
        other_room = next(
            room
            for room in self.storage.rooms.values()
            if room.id != self.room.id
        )
        other_category = other_client.post(
            f"/rooms/{other_room.id}/categories",
            data={"name": "Other"},
        )
        self.assertEqual(other_category.status_code, 302)
        data = self.expense_data(category)
        data["category_id"] = next(
            category.id
            for category in self.storage.categories.values()
            if category.room_id == other_room.id
        )

        wrong_room_category = self.owner.post(
            f"/rooms/{self.room.id}/expenses/new",
            data=data,
        )
        self.assertEqual(wrong_room_category.status_code, 400)
        self.assertIn(b"Choose a category for this room.", wrong_room_category.data)
        self.assertEqual(self.storage.expenses, {})


if __name__ == "__main__":
    unittest.main()
