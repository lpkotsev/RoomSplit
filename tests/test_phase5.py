import unittest
from datetime import date
from decimal import Decimal

from roomsplit import create_app
from roomsplit.balances import calculate_room_balances


TEST_SECRET_KEY = "phase-five-test-secret"


class PhaseFiveTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {"TESTING": True, "SECRET_KEY": TEST_SECRET_KEY}
        )
        self.storage = self.app.extensions["roomsplit_storage"]
        self.owner, self.owner_id = self.create_user("owner")
        self.owner.post("/rooms/create", data={"name": "Shared event", "password": "room-password"})
        self.room = next(iter(self.storage.rooms.values()))
        self.member, self.member_id = self.create_user("member")
        self.join_room(self.member)
        self.category = self.create_category()
        self.expense = self.create_expense(
            {
                self.owner_id: "10.00",
            }
        )

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

    def join_room(self, client):
        response = client.post(
            "/rooms/join",
            data={
                "room_code": self.room.code,
                "password": "room-password",
            },
        )
        self.assertEqual(response.status_code, 302)

    def create_category(self):
        response = self.owner.post(
            f"/rooms/{self.room.id}/categories",
            data={"name": "Shared costs"},
        )
        self.assertEqual(response.status_code, 302)
        return next(iter(self.storage.categories.values()))

    def create_expense(
        self,
        payer_amounts,
        amount="10.00",
        split_type="equal",
        custom_shares=None,
    ):
        data = {
            "item": "Groceries",
            "amount": amount,
            "date": "2026-08-03",
            "category_id": self.category.id,
            "split_type": split_type,
        }
        if split_type == "equal":
            data["remainder_payer_id"] = self.owner_id
        data.update(
            {
                f"payer_{member_id}": amount
                for member_id, amount in payer_amounts.items()
            }
        )
        if custom_shares is not None:
            data.update(
                {
                    f"share_{member_id}": share
                    for member_id, share in custom_shares.items()
                }
            )
        stored_ids = set(self.storage.expenses)
        response = self.owner.post(
            f"/rooms/{self.room.id}/expenses/new",
            data=data,
        )
        self.assertEqual(response.status_code, 302)
        return next(
            expense
            for expense_id, expense in self.storage.expenses.items()
            if expense_id not in stored_ids
        )

    def balances(self):
        return calculate_room_balances(
            self.storage.expenses.values(),
            member_ids=self.room.member_ids,
            repayments=self.storage.repayments.values(),
        )

    def repayment_data(
        self,
        amount="3.00",
        payer_id=None,
        recipient_id=None,
        **overrides,
    ):
        data = {
            "payer_id": payer_id or self.member_id,
            "recipient_id": recipient_id or self.owner_id,
            "amount": amount,
            "date": "2026-08-05",
            "note": "settlement",
        }
        data.update(overrides)
        return data

    def test_member_can_record_repayment_and_balance_changes_between_members(self):
        self.assertEqual(
            self.member.get(
                f"/rooms/{self.room.id}/repayments/new"
            ).status_code,
            200,
        )
        response = self.member.post(
            f"/rooms/{self.room.id}/repayments/new",
            data=self.repayment_data(),
        )

        self.assertEqual(response.status_code, 302)
        repayment = next(iter(self.storage.repayments.values()))
        self.assertEqual(repayment.payer_id, self.member_id)
        self.assertEqual(repayment.recipient_id, self.owner_id)
        self.assertEqual(repayment.amount, Decimal("3.00"))
        self.assertEqual(repayment.repayment_date, date(2026, 8, 5))
        self.assertEqual(repayment.note, "settlement")
        self.assertEqual(
            self.balances(),
            {
                self.owner_id: Decimal("2.00"),
                self.member_id: Decimal("-2.00"),
            },
        )

    def test_repayment_cannot_exceed_current_balance_between_members(self):
        response = self.member.post(
            f"/rooms/{self.room.id}/repayments/new",
            data=self.repayment_data("5.01"),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Repayment exceeds the current balance between these members.", response.data)
        self.assertEqual(self.storage.repayments, {})
        self.assertEqual(self.balances()[self.member_id], Decimal("-5.00"))

    def test_repayment_amounts_must_be_positive_cents(self):
        invalid_repayments = ("0.00", "1.001", "-1.00")
        for amount in invalid_repayments:
            with self.subTest(kind="repayment", amount=amount):
                response = self.member.post(
                    f"/rooms/{self.room.id}/repayments/new",
                    data=self.repayment_data(amount),
                )
                self.assertEqual(response.status_code, 400)
        self.assertEqual(self.storage.repayments, {})

    def test_nonmember_cannot_read_or_record_repayments(self):
        outsider, _ = self.create_user("outsider")
        path = f"/rooms/{self.room.id}/repayments/new"
        self.assertEqual(outsider.get(path).status_code, 403)
        self.assertEqual(outsider.post(path, data=self.repayment_data()).status_code, 403)
        self.assertEqual(self.storage.repayments, {})

    def test_creator_can_edit_or_delete_repayment_but_owner_cannot_manage_others(self):
        created = self.member.post(
            f"/rooms/{self.room.id}/repayments/new",
            data=self.repayment_data("2.00"),
        )
        self.assertEqual(created.status_code, 302)
        repayment = next(iter(self.storage.repayments.values()))

        denied_edit = self.owner.post(
            f"/rooms/{self.room.id}/repayments/{repayment.id}/edit",
            data=self.repayment_data("1.00"),
        )
        denied_delete = self.owner.post(
            f"/rooms/{self.room.id}/repayments/{repayment.id}/delete",
        )
        self.assertEqual(denied_edit.status_code, 403)
        self.assertEqual(denied_delete.status_code, 403)

        allowed_edit = self.member.post(
            f"/rooms/{self.room.id}/repayments/{repayment.id}/edit",
            data=self.repayment_data("1.00"),
        )
        self.assertEqual(allowed_edit.status_code, 302)
        self.assertEqual(
            self.storage.repayments[repayment.id].amount,
            Decimal("1.00"),
        )
        allowed_delete = self.member.post(
            f"/rooms/{self.room.id}/repayments/{repayment.id}/delete",
        )
        self.assertEqual(allowed_delete.status_code, 302)
        self.assertEqual(self.storage.repayments, {})

    def test_administrator_can_edit_and_delete_repayment(self):
        created = self.member.post(
            f"/rooms/{self.room.id}/repayments/new",
            data=self.repayment_data("2.00"),
        )
        self.assertEqual(created.status_code, 302)
        repayment = next(iter(self.storage.repayments.values()))
        administrator, administrator_id = self.create_user("administrator")
        self.join_room(administrator)
        self.owner.post(
            f"/rooms/{self.room.id}/administrator",
            data={"member_id": administrator_id},
        )

        allowed_edit = administrator.post(
            f"/rooms/{self.room.id}/repayments/{repayment.id}/edit",
            data=self.repayment_data("1.00"),
        )
        self.assertEqual(allowed_edit.status_code, 302)
        allowed_delete = administrator.post(
            f"/rooms/{self.room.id}/repayments/{repayment.id}/delete",
        )
        self.assertEqual(allowed_delete.status_code, 302)
        self.assertEqual(self.storage.repayments, {})

    def test_repayment_changes_that_overpay_later_records_are_rejected(self):
        first = self.member.post(
            f"/rooms/{self.room.id}/repayments/new",
            data=self.repayment_data("2.00", **{"date": "2026-08-05"}),
        )
        second = self.member.post(
            f"/rooms/{self.room.id}/repayments/new",
            data=self.repayment_data("2.00", **{"date": "2026-08-06"}),
        )
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        repayment = next(iter(self.storage.repayments.values()))

        update = self.member.post(
            f"/rooms/{self.room.id}/repayments/{repayment.id}/edit",
            data=self.repayment_data("4.00", **{"date": "2026-08-05"}),
        )

        self.assertEqual(update.status_code, 400)
        self.assertEqual(repayment.amount, Decimal("2.00"))
        self.assertEqual(len(self.storage.repayments), 2)



if __name__ == "__main__":
    unittest.main()
