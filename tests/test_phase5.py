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
        self.owner.post("/rooms/create", data={"password": "room-password"})
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
            refunds=self.storage.refunds.values(),
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

    def refund_data(
        self,
        amount="2.00",
        expense_id=None,
        payer_amounts=None,
        **overrides,
    ):
        data = {
            "expense_id": (
                self.expense.id if expense_id is None else expense_id
            ),
            "amount": amount,
            "date": "2026-08-06",
            "note": "store refund",
        }
        if payer_amounts is not None:
            data.update(
                {
                    f"payer_{member_id}": value
                    for member_id, value in payer_amounts.items()
                }
            )
        data.update(overrides)
        return data

    def test_member_can_record_repayment_and_balance_changes_between_members(self):
        self.assertEqual(
            self.member.get(
                f"/rooms/{self.room.id}/repayments/new"
            ).status_code,
            200,
        )
        self.assertEqual(
            self.member.get(
                f"/rooms/{self.room.id}/refunds/new"
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

    def test_repayment_and_refund_amounts_must_be_positive_cents(self):
        invalid_repayments = ("0.00", "1.001", "-1.00")
        for amount in invalid_repayments:
            with self.subTest(kind="repayment", amount=amount):
                response = self.member.post(
                    f"/rooms/{self.room.id}/repayments/new",
                    data=self.repayment_data(amount),
                )
                self.assertEqual(response.status_code, 400)
        self.assertEqual(self.storage.repayments, {})

        invalid_refunds = ("0.00", "1.001", "-1.00")
        for amount in invalid_refunds:
            with self.subTest(kind="refund", amount=amount):
                response = self.member.post(
                    f"/rooms/{self.room.id}/refunds/new",
                    data=self.refund_data(
                        amount,
                        payer_amounts={self.owner_id: amount},
                    ),
                )
                self.assertEqual(response.status_code, 400)
        self.assertEqual(self.storage.refunds, {})

    def test_nonmember_cannot_read_or_record_repayments_or_refunds(self):
        outsider, _ = self.create_user("outsider")

        for path, data in (
            (
                f"/rooms/{self.room.id}/repayments/new",
                self.repayment_data(),
            ),
            (
                f"/rooms/{self.room.id}/refunds/new",
                self.refund_data(payer_amounts={self.owner_id: "2.00"}),
            ),
        ):
            with self.subTest(path=path):
                self.assertEqual(outsider.get(path).status_code, 403)
                self.assertEqual(
                    outsider.post(path, data=data).status_code,
                    403,
                )
        self.assertEqual(self.storage.repayments, {})
        self.assertEqual(self.storage.refunds, {})

    def test_linked_partial_refund_reduces_payer_contribution_and_shares(self):
        response = self.member.post(
            f"/rooms/{self.room.id}/refunds/new",
            data=self.refund_data(
                "2.00",
                payer_amounts={self.owner_id: "2.00"},
            ),
        )

        self.assertEqual(response.status_code, 302)
        refund = next(iter(self.storage.refunds.values()))
        self.assertEqual(refund.expense_id, self.expense.id)
        self.assertEqual(refund.amount, Decimal("2.00"))
        self.assertEqual(refund.payer_amounts[self.owner_id], Decimal("2.00"))
        self.assertEqual(
            self.balances(),
            {
                self.owner_id: Decimal("4.00"),
                self.member_id: Decimal("-4.00"),
            },
        )

    def test_unlinked_refund_does_not_change_room_balances(self):
        before = self.balances()

        response = self.member.post(
            f"/rooms/{self.room.id}/refunds/new",
            data=self.refund_data(
                "2.00",
                expense_id="",
                payer_amounts=None,
            ),
        )

        self.assertEqual(response.status_code, 302)
        refund = next(iter(self.storage.refunds.values()))
        self.assertIsNone(refund.expense_id)
        self.assertEqual(self.balances(), before)

    def test_full_refund_reverses_expense_and_repeated_partials_cannot_overrefund(self):
        first = self.member.post(
            f"/rooms/{self.room.id}/refunds/new",
            data=self.refund_data(
                "4.00",
                payer_amounts={self.owner_id: "4.00"},
            ),
        )
        self.assertEqual(first.status_code, 302)

        final = self.owner.post(
            f"/rooms/{self.room.id}/refunds/new",
            data=self.refund_data(
                "6.00",
                payer_amounts={self.owner_id: "6.00"},
            ),
        )
        self.assertEqual(final.status_code, 302)
        self.assertEqual(
            self.balances(),
            {
                self.owner_id: Decimal("0.00"),
                self.member_id: Decimal("0.00"),
            },
        )

        excess = self.owner.post(
            f"/rooms/{self.room.id}/refunds/new",
            data=self.refund_data(
                "0.01",
                payer_amounts={self.owner_id: "0.01"},
            ),
        )
        self.assertEqual(excess.status_code, 400)
        self.assertIn(b"Refund exceeds the remaining refundable amount.", excess.data)
        self.assertEqual(len(self.storage.refunds), 2)

    def test_partial_refund_on_multiple_payers_requires_allocated_payer_amounts(self):
        self.expense = self.create_expense(
            {
                self.owner_id: "4.00",
                self.member_id: "6.00",
            }
        )
        original = next(
            expense
            for expense_id, expense in self.storage.expenses.items()
            if expense_id != self.expense.id
        )
        del self.storage.expenses[original.id]

        response = self.member.post(
            f"/rooms/{self.room.id}/refunds/new",
            data=self.refund_data("3.00", payer_amounts=None),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Refund payer amounts must equal the refund total.", response.data)

        response = self.member.post(
            f"/rooms/{self.room.id}/refunds/new",
            data=self.refund_data(
                "3.00",
                payer_amounts={
                    self.owner_id: "1.00",
                    self.member_id: "2.00",
                },
            ),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            self.balances(),
            {
                self.owner_id: Decimal("-0.50"),
                self.member_id: Decimal("0.50"),
            },
        )

    def test_refund_share_rounding_breaks_ties_for_original_remainder_payer(self):
        expense = self.create_expense(
            {self.owner_id: "0.02"},
            amount="0.02",
        )
        before = self.balances()

        response = self.member.post(
            f"/rooms/{self.room.id}/refunds/new",
            data=self.refund_data(
                "0.01",
                expense_id=expense.id,
                payer_amounts={self.owner_id: "0.01"},
            ),
        )

        self.assertEqual(response.status_code, 302)
        after = self.balances()
        self.assertEqual(after[self.owner_id] - before[self.owner_id], Decimal("0.00"))
        self.assertEqual(after[self.member_id] - before[self.member_id], Decimal("0.00"))

    def test_refund_share_rounding_uses_largest_fraction_for_custom_split(self):
        expense = self.create_expense(
            {self.owner_id: "0.05"},
            amount="0.05",
            split_type="custom",
            custom_shares={
                self.owner_id: "0.02",
                self.member_id: "0.03",
            },
        )
        before = self.balances()

        response = self.member.post(
            f"/rooms/{self.room.id}/refunds/new",
            data=self.refund_data(
                "0.01",
                expense_id=expense.id,
                payer_amounts={self.owner_id: "0.01"},
            ),
        )

        self.assertEqual(response.status_code, 302)
        after = self.balances()
        self.assertEqual(after[self.owner_id] - before[self.owner_id], Decimal("-0.01"))
        self.assertEqual(after[self.member_id] - before[self.member_id], Decimal("0.01"))

    def test_refund_amount_cannot_exceed_original_payer_contribution(self):
        self.expense = self.create_expense(
            {
                self.owner_id: "9.00",
                self.member_id: "1.00",
            }
        )
        response = self.member.post(
            f"/rooms/{self.room.id}/refunds/new",
            data=self.refund_data(
                "2.00",
                payer_amounts={self.member_id: "2.00"},
            ),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Refund allocation exceeds that payer", response.data)
        self.assertEqual(self.storage.refunds, {})

    def test_only_creator_can_edit_or_delete_refund(self):
        created = self.member.post(
            f"/rooms/{self.room.id}/refunds/new",
            data=self.refund_data(
                "2.00",
                payer_amounts={self.owner_id: "2.00"},
            ),
        )
        self.assertEqual(created.status_code, 302)
        refund = next(iter(self.storage.refunds.values()))

        denied_edit = self.owner.post(
            f"/rooms/{self.room.id}/refunds/{refund.id}/edit",
            data=self.refund_data(
                "3.00",
                payer_amounts={self.owner_id: "3.00"},
            ),
        )
        denied_delete = self.owner.post(
            f"/rooms/{self.room.id}/refunds/{refund.id}/delete",
        )
        self.assertEqual(denied_edit.status_code, 403)
        self.assertEqual(denied_delete.status_code, 403)

        allowed_edit = self.member.post(
            f"/rooms/{self.room.id}/refunds/{refund.id}/edit",
            data=self.refund_data(
                "3.00",
                payer_amounts={self.owner_id: "3.00"},
            ),
        )
        self.assertEqual(allowed_edit.status_code, 302)
        self.assertEqual(
            self.storage.refunds[refund.id].amount,
            Decimal("3.00"),
        )
        allowed_delete = self.member.post(
            f"/rooms/{self.room.id}/refunds/{refund.id}/delete",
        )
        self.assertEqual(allowed_delete.status_code, 302)
        self.assertEqual(self.storage.refunds, {})

    def test_only_owner_or_administrator_can_edit_or_delete_repayment(self):
        created = self.member.post(
            f"/rooms/{self.room.id}/repayments/new",
            data=self.repayment_data("2.00"),
        )
        self.assertEqual(created.status_code, 302)
        repayment = next(iter(self.storage.repayments.values()))

        denied_edit = self.member.post(
            f"/rooms/{self.room.id}/repayments/{repayment.id}/edit",
            data=self.repayment_data("1.00"),
        )
        denied_delete = self.member.post(
            f"/rooms/{self.room.id}/repayments/{repayment.id}/delete",
        )
        self.assertEqual(denied_edit.status_code, 403)
        self.assertEqual(denied_delete.status_code, 403)

        allowed_edit = self.owner.post(
            f"/rooms/{self.room.id}/repayments/{repayment.id}/edit",
            data=self.repayment_data("1.00"),
        )
        self.assertEqual(allowed_edit.status_code, 302)
        self.assertEqual(
            self.storage.repayments[repayment.id].amount,
            Decimal("1.00"),
        )
        allowed_delete = self.owner.post(
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

        update = self.owner.post(
            f"/rooms/{self.room.id}/repayments/{repayment.id}/edit",
            data=self.repayment_data("4.00", **{"date": "2026-08-05"}),
        )

        self.assertEqual(update.status_code, 400)
        self.assertEqual(repayment.amount, Decimal("2.00"))
        self.assertEqual(len(self.storage.repayments), 2)

    def test_refund_edit_that_overpays_an_existing_repayment_is_rejected(self):
        repayment = self.member.post(
            f"/rooms/{self.room.id}/repayments/new",
            data=self.repayment_data("3.00"),
        )
        self.assertEqual(repayment.status_code, 302)
        created = self.member.post(
            f"/rooms/{self.room.id}/refunds/new",
            data=self.refund_data(
                "1.00",
                payer_amounts={self.owner_id: "1.00"},
            ),
        )
        self.assertEqual(created.status_code, 302)
        refund = next(iter(self.storage.refunds.values()))

        update = self.member.post(
            f"/rooms/{self.room.id}/refunds/{refund.id}/edit",
            data=self.refund_data(
                "5.00",
                payer_amounts={self.owner_id: "5.00"},
            ),
        )

        self.assertEqual(update.status_code, 400)
        self.assertEqual(refund.amount, Decimal("1.00"))
        self.assertEqual(len(self.storage.refunds), 1)


if __name__ == "__main__":
    unittest.main()
