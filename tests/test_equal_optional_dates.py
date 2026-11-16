import unittest
from datetime import date
from decimal import Decimal

from roomsplit import create_app
from roomsplit.splits import calculate_expense_shares


class EqualOptionalDateTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SECRET_KEY": "optional-date-test"})
        self.storage = self.app.extensions["roomsplit_storage"]
        self.owner, self.owner_id = self.create_user("owner")
        self.owner.post("/rooms/create", data={"name": "Event", "password": "room"})
        self.room = next(iter(self.storage.rooms.values()))
        self.member, self.member_id = self.create_user("member")
        self.third, self.third_id = self.create_user("third")
        for client in (self.member, self.third):
            self.assertEqual(
                client.post(
                    "/rooms/join",
                    data={"room_code": self.room.code, "password": "room"},
                ).status_code,
                302,
            )
        self.expense_url = f"/rooms/{self.room.id}/expenses/new"

    def create_user(self, username):
        client = self.app.test_client()
        data = {"username": username, "password": "synthetic-password"}
        self.assertEqual(client.post("/register", data=data).status_code, 302)
        self.assertEqual(client.post("/sign-in", data=data).status_code, 302)
        account = next(a for a in self.storage.accounts.values() if a.username == username)
        return client, account.id

    def expense_data(self):
        return {
            "item": "Meal",
            "amount": "10.00",
            "category_name": "Restaurant",
            f"payer_{self.owner_id}": "6.00",
            f"payer_{self.member_id}": "4.00",
        }

    def test_form_has_optional_date_and_split_choices(self):
        page = self.owner.get(self.expense_url)
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'name="split_type"', page.data)
        self.assertIn(b"Custom split", page.data)
        self.assertIn(f'name="share_{self.owner_id}"'.encode(), page.data)
        self.assertNotIn(b'name="remainder_payer_id"', page.data)
        self.assertIn(b"Date (optional)", page.data)
        for path in ("repayments/new",):
            self.assertIn(
                b"Date (optional)",
                self.owner.get(f"/rooms/{self.room.id}/{path}").data,
            )

    def test_largest_payer_receives_remainder_and_blank_date_is_today(self):
        data = self.expense_data()
        data["remainder_payer_id"] = self.member_id
        response = self.owner.post(self.expense_url, data=data)
        self.assertEqual(response.status_code, 302)
        expense = next(iter(self.storage.expenses.values()))
        self.assertEqual(expense.expense_date, date.today())
        self.assertEqual(expense.remainder_payer_id, self.owner_id)
        self.assertEqual(expense.split_type, "equal")
        self.assertIsNone(expense.custom_shares)
        self.assertEqual(
            calculate_expense_shares(expense),
            {
                self.owner_id: Decimal("3.34"),
                self.member_id: Decimal("3.33"),
                self.third_id: Decimal("3.33"),
            },
        )

    def test_tied_largest_payers_must_be_chosen_even_without_remainder(self):
        data = self.expense_data()
        data[f"payer_{self.owner_id}"] = "5.00"
        data[f"payer_{self.member_id}"] = "5.00"
        missing = self.owner.post(self.expense_url, data=data)
        self.assertEqual(missing.status_code, 400)
        self.assertIn(b"Choose one of the highest payers", missing.data)
        self.assertIn(b'name="remainder_payer_id"', missing.data)
        self.assertNotIn(self.third_id.encode(), missing.data.split(b'id="remainder-payer"')[1].split(b"</select>")[0])
        self.assertEqual(self.storage.expenses, {})
        data["remainder_payer_id"] = self.third_id
        invalid = self.owner.post(self.expense_url, data=data)
        self.assertEqual(invalid.status_code, 400)
        data["remainder_payer_id"] = self.member_id
        self.assertEqual(self.owner.post(self.expense_url, data=data).status_code, 302)
        expense = next(iter(self.storage.expenses.values()))
        self.assertEqual(calculate_expense_shares(expense)[self.member_id], Decimal("3.34"))

        data["amount"] = "12.00"
        data[f"payer_{self.owner_id}"] = "6.00"
        data[f"payer_{self.member_id}"] = "6.00"
        del data["remainder_payer_id"]
        self.assertEqual(self.owner.post(self.expense_url, data=data).status_code, 400)

    def test_custom_split_requires_shares_to_match_total(self):
        response = self.owner.post(
            self.expense_url, data={**self.expense_data(), "split_type": "custom"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Custom shares must equal the expense total", response.data)
        self.assertEqual(self.storage.expenses, {})

    def test_optional_dates_on_create_and_edit_and_invalid_dates(self):
        self.assertEqual(self.owner.post(self.expense_url, data=self.expense_data()).status_code, 302)
        repayment_url = f"/rooms/{self.room.id}/repayments/new"
        repayment_data = {
            "payer_id": self.third_id,
            "recipient_id": self.owner_id,
            "amount": "1.00",
        }
        self.assertEqual(self.third.post(repayment_url, data=repayment_data).status_code, 302)
        repayment = next(iter(self.storage.repayments.values()))
        self.assertEqual(repayment.repayment_date, date.today())
        repayment_edit = f"/rooms/{self.room.id}/repayments/{repayment.id}/edit"
        self.assertEqual(self.third.post(repayment_edit, data={**repayment_data, "date": ""}).status_code, 302)
        self.assertEqual(self.storage.repayments[repayment.id].repayment_date, date.today())

        for client, path, data in (
            (self.owner, self.expense_url, self.expense_data()),
            (self.third, repayment_url, repayment_data),
        ):
            with self.subTest(path=path):
                response = client.post(path, data={**data, "date": "not-a-date"})
                self.assertEqual(response.status_code, 400)
                self.assertIn(b"Enter a valid", response.data)


if __name__ == "__main__":
    unittest.main()
